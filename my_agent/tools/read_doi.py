import os
import tempfile
import httpx
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

_MAX_TEXT_CHARS = 100_000
_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
_UNPAYWALL_EMAIL = os.environ.get("UNPAYWALL_EMAIL", "agent@example.com")
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def read_doi(doi: str) -> str:
    """Look up a DOI and return the document's content.

    Tries multiple strategies to get the actual text:
    1. Open-access PDF via Unpaywall, Semantic Scholar, DOI redirect
    2. Scrape the DOI landing page for chapter descriptions / content
    3. Google Books API for content snippets
    4. Open Library / Internet Archive for free copies

    If no full text is available, returns whatever content it found
    (landing page text, chapter descriptions, snippets) plus metadata.

    Args:
        doi: The DOI string, e.g. "10.1353/book.24372".

    Returns:
        The document text (ideally full PDF), or landing page content
        plus metadata, or an error with title/authors for follow-up.
    """
    doi = doi.strip()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")

    # Step 1: Get metadata from CrossRef
    metadata = _get_crossref_metadata(doi)
    title = metadata.get("title", "Unknown")
    authors = metadata.get("authors", "Unknown")

    # Step 2: Try to get full PDF text
    if _HAS_FITZ:
        pdf_urls = []
        pdf_urls.extend(_urls_from_unpaywall(doi))
        pdf_urls.extend(_urls_from_semantic_scholar(doi))

        seen = set()
        for url in pdf_urls:
            if url and url not in seen:
                seen.add(url)
                result = _download_pdf(url)
                if result and not result.startswith("Error:"):
                    return result

    # Step 3: Follow DOI redirect and scrape the landing page
    landing_text = _scrape_doi_landing_page(doi)

    # Step 4: Try Google Books for content snippets
    gbooks_text = _try_google_books(title, authors)

    # Step 5: Try Open Library / Internet Archive
    archive_text = _try_open_library(title, authors)

    # Combine whatever we found
    parts = []
    if landing_text:
        parts.append(f"=== Content from DOI landing page ===\n{landing_text}")
    if gbooks_text:
        parts.append(f"=== Content from Google Books ===\n{gbooks_text}")
    if archive_text:
        parts.append(f"=== Content from Open Library ===\n{archive_text}")

    if parts:
        header = f"Title: {title}\nAuthors: {authors}\n\n"
        combined = header + "\n\n".join(parts)
        if len(combined) > _MAX_TEXT_CHARS:
            combined = combined[:_MAX_TEXT_CHARS] + "\n\n[Truncated]"
        return combined

    return (
        f"Could not access content for DOI '{doi}'.\n"
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        "Use web_search to find this document by title, or search for "
        "reviews/chapter summaries that discuss its content."
    )


# ── CrossRef metadata ────────────────────────────────────────────────

def _get_crossref_metadata(doi: str) -> dict:
    try:
        resp = httpx.get(
            f"https://api.crossref.org/works/{doi}",
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
        msg = resp.json().get("message", {})

        title_list = msg.get("title", [])
        title = title_list[0] if title_list else "Unknown"

        authors_list = msg.get("author", [])
        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in authors_list
        ) or "Unknown"

        return {"title": title, "authors": authors}
    except Exception:
        return {"title": "Unknown", "authors": "Unknown"}


# ── PDF URL finders ───────────────────────────────────────────────────

def _urls_from_unpaywall(doi: str) -> list[str]:
    try:
        resp = httpx.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": _UNPAYWALL_EMAIL},
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    urls = []
    best = data.get("best_oa_location")
    if best:
        for key in ("url_for_pdf", "url_for_landing_page"):
            if best.get(key):
                urls.append(best[key])
    for loc in data.get("oa_locations", []):
        if loc.get("url_for_pdf"):
            urls.append(loc["url_for_pdf"])
    return urls


def _urls_from_semantic_scholar(doi: str) -> list[str]:
    try:
        resp = httpx.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "openAccessPdf"},
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
        oa = resp.json().get("openAccessPdf")
        if oa and oa.get("url"):
            return [oa["url"]]
    except Exception:
        pass
    return []


# ── Landing page scraping ─────────────────────────────────────────────

def _scrape_doi_landing_page(doi: str) -> str | None:
    """Follow DOI, scrape whatever text the landing page has."""
    try:
        resp = httpx.get(
            f"https://doi.org/{doi}",
            headers={**_HEADERS, "Accept": "text/html,*/*"},
            timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return None

    content_type = resp.headers.get("content-type", "")
    if "application/pdf" in content_type or resp.content[:5] == b"%PDF-":
        # Unexpectedly got a PDF — try to extract it
        if _HAS_FITZ:
            result = _extract_pdf_bytes(resp.content)
            if not result.startswith("Error:"):
                return result
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

    for tag in soup(["script", "style", "nav", "noscript", "iframe"]):
        tag.decompose()

    # Try to get the main content area
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(class_="content")
        or soup.find("body")
        or soup
    )

    text = main.get_text(separator="\n", strip=True)
    lines = [l for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)

    if len(text) < 100:
        return None  # Too little content to be useful

    # Truncate very long landing pages
    if len(text) > 50_000:
        text = text[:50_000] + "\n[Truncated]"

    return text


# ── Google Books ──────────────────────────────────────────────────────

def _try_google_books(title: str, authors: str) -> str | None:
    """Search Google Books API for content snippets."""
    if title == "Unknown":
        return None

    query = f"{title} {authors}".strip()
    try:
        resp = httpx.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": 3},
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    items = data.get("items", [])
    if not items:
        return None

    parts = []
    for item in items:
        info = item.get("volumeInfo", {})
        item_title = info.get("title", "")
        item_desc = info.get("description", "")
        preview_link = info.get("previewLink", "")

        if item_desc:
            parts.append(f"Title: {item_title}\n{item_desc}")

        # Try to fetch the Google Books preview page for more content
        if preview_link:
            preview_text = _fetch_html_text(preview_link)
            if preview_text and len(preview_text) > 200:
                parts.append(f"Google Books preview content:\n{preview_text}")

    return "\n\n".join(parts) if parts else None


# ── Open Library / Internet Archive ───────────────────────────────────

def _try_open_library(title: str, authors: str) -> str | None:
    """Search Open Library for a free version."""
    if title == "Unknown":
        return None

    try:
        resp = httpx.get(
            "https://openlibrary.org/search.json",
            params={"title": title, "limit": 3},
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    docs = data.get("docs", [])
    if not docs:
        return None

    parts = []
    for doc in docs:
        ol_title = doc.get("title", "")
        ol_key = doc.get("key", "")
        has_fulltext = doc.get("has_fulltext", False)

        if ol_key:
            # Try to fetch the Open Library page for descriptions / content
            ol_url = f"https://openlibrary.org{ol_key}"
            page_text = _fetch_html_text(ol_url)
            if page_text and len(page_text) > 100:
                parts.append(f"Open Library ({ol_title}):\n{page_text}")

            # If it has full text on Internet Archive, try to get it
            if has_fulltext:
                ia_ids = doc.get("ia", [])
                for ia_id in ia_ids[:1]:  # Just try the first one
                    ia_text = _try_internet_archive(ia_id)
                    if ia_text:
                        parts.append(f"Internet Archive text:\n{ia_text}")

    return "\n\n".join(parts) if parts else None


def _try_internet_archive(ia_id: str) -> str | None:
    """Try to get text content from Internet Archive."""
    # IA provides a plaintext endpoint for some books
    try:
        resp = httpx.get(
            f"https://archive.org/stream/{ia_id}/{ia_id}_djvu.txt",
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        if resp.status_code == 200 and len(resp.text) > 500:
            text = resp.text
            if len(text) > _MAX_TEXT_CHARS:
                text = text[:_MAX_TEXT_CHARS] + "\n[Truncated]"
            return text
    except Exception:
        pass
    return None


# ── Utility functions ─────────────────────────────────────────────────

def _fetch_html_text(url: str) -> str | None:
    """Fetch a URL and return its plain text content."""
    try:
        resp = httpx.get(
            url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return None

    if "application/pdf" in resp.headers.get("content-type", ""):
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

    for tag in soup(["script", "style", "nav", "noscript", "iframe"]):
        tag.decompose()

    main = (
        soup.find("main") or soup.find("article")
        or soup.find("body") or soup
    )
    text = main.get_text(separator="\n", strip=True)
    lines = [l for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)

    if len(text) > 30_000:
        text = text[:30_000] + "\n[Truncated]"

    return text if len(text) > 50 else None


def _download_pdf(url: str) -> str | None:
    """Try to download a PDF from a URL and extract text."""
    dl_timeout = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)
    try:
        with httpx.stream(
            "GET", url,
            headers={**_HEADERS, "Accept": "application/pdf,*/*"},
            timeout=dl_timeout, follow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            chunks = []
            total = 0
            for chunk in resp.iter_bytes(chunk_size=65_536):
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    return "Error: PDF too large."
                chunks.append(chunk)
            raw = b"".join(chunks)

    except Exception as e:
        return f"Error: {e}"

    if raw[:5] != b"%PDF-" and "application/pdf" not in content_type:
        return f"Error: Not a PDF"

    return _extract_pdf_bytes(raw)


def _extract_pdf_bytes(raw: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        return f"Error: {e}"

    if doc.page_count == 0:
        doc.close()
        return "Error: PDF has no pages."

    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append(f"--- Page {i} ---\n{text}")
        else:
            pages.append(f"--- Page {i} ---\n[No extractable text]")
    doc.close()

    full_text = "\n\n".join(pages)
    if len(full_text) > _MAX_TEXT_CHARS:
        full_text = full_text[:_MAX_TEXT_CHARS] + "\n[Truncated]"
    return full_text
