import os
import tempfile
import httpx

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

_MAX_TEXT_CHARS = 100_000
_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024

# Unpaywall is free, just needs any email
_UNPAYWALL_EMAIL = os.environ.get(
    "UNPAYWALL_EMAIL", "ashley.lo@student.uva.nl")


def read_doi(doi: str) -> str:
    """Look up a DOI and read the full text of the associated PDF.

    This tool resolves a DOI to its open-access PDF using the Unpaywall API,
    downloads the PDF, and extracts text from every page.

    Use this tool whenever a question mentions a DOI (e.g. "10.1353/book.24372").
    Pass ONLY the DOI string, not a full URL.

    Args:
        doi: The DOI identifier, e.g. "10.1353/book.24372".
             Do NOT include "https://doi.org/" — just the DOI itself.

    Returns:
        The full text of the PDF with page separators, or an error message.
    """
    if not _HAS_FITZ:
        return "Error: PyMuPDF is not installed."

    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")

    # Step 1: Find the open-access PDF URL via Unpaywall
    pdf_url = _find_pdf_url(doi)
    if pdf_url is None:
        return (
            f"Error: Could not find an open-access PDF for DOI '{doi}'. "
            "Try using web_search to find the document by title instead."
        )

    # Step 2: Download and extract text
    return _download_and_extract(pdf_url, doi)


def _find_pdf_url(doi: str) -> str | None:
    """Query the Unpaywall API for an open-access PDF URL."""
    unpaywall_url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": _UNPAYWALL_EMAIL}

    try:
        resp = httpx.get(unpaywall_url, params=params, timeout=10,
                         follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # Fallback: try resolving the DOI directly — some resolve to PDFs
        return _try_doi_redirect(doi)

    # Try best open-access location first
    best = data.get("best_oa_location")
    if best:
        url = best.get("url_for_pdf") or best.get("url_for_landing_page")
        if url:
            return url

    # Try all OA locations
    for loc in data.get("oa_locations", []):
        url = loc.get("url_for_pdf")
        if url:
            return url

    # Last resort: try the DOI redirect itself
    return _try_doi_redirect(doi)


def _try_doi_redirect(doi: str) -> str | None:
    """Follow the DOI redirect and see if it lands on a PDF."""
    try:
        resp = httpx.head(
            f"https://doi.org/{doi}",
            follow_redirects=True,
            timeout=10,
            headers={"Accept": "application/pdf,*/*"},
        )
        final_url = str(resp.url)
        content_type = resp.headers.get("content-type", "")

        if "application/pdf" in content_type or final_url.endswith(".pdf"):
            return final_url

        # Return the landing page URL — maybe read_pdf or fetch_webpage
        # can do something with it
        return final_url
    except Exception:
        return None


def _download_and_extract(url: str, doi: str) -> str:
    """Download a PDF from a URL and extract its text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/octet-stream,*/*",
    }
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)

    try:
        with httpx.stream("GET", url, headers=headers, timeout=timeout,
                          follow_redirects=True) as resp:
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            final_url = str(resp.url)

            # If we landed on an HTML page instead of a PDF, return info
            if ("text/html" in content_type
                    and "application/pdf" not in content_type
                    and not final_url.endswith(".pdf")):
                return (
                    f"The DOI '{doi}' resolved to an HTML page, not a PDF: "
                    f"{final_url}\n"
                    "Use fetch_webpage on this URL to read the page, or "
                    "use web_search to find a direct PDF link."
                )

            total = 0
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            try:
                for chunk in resp.iter_bytes(chunk_size=65_536):
                    total += len(chunk)
                    if total > _MAX_DOWNLOAD_BYTES:
                        tmp.close()
                        os.unlink(tmp.name)
                        return f"Error: PDF exceeds {_MAX_DOWNLOAD_BYTES // (1024*1024)} MB."
                    tmp.write(chunk)
                tmp.close()
            except Exception as e:
                tmp.close()
                os.unlink(tmp.name)
                raise e

    except httpx.HTTPStatusError as e:
        return (
            f"Error: HTTP {e.response.status_code} downloading PDF for DOI '{doi}'. "
            "Try web_search to find an alternative source."
        )
    except Exception as e:
        return f"Error: Could not download PDF — {e}"

    # Extract text
    try:
        doc = fitz.open(tmp.name)
        if doc.page_count == 0:
            doc.close()
            os.unlink(tmp.name)
            return "Error: PDF has no pages."

        pages = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(f"--- Page {i} ---\n{text}")
            else:
                pages.append(f"--- Page {i} ---\n[No extractable text]")
        doc.close()
    finally:
        os.unlink(tmp.name)

    full_text = "\n\n".join(pages)
    if len(full_text) > _MAX_TEXT_CHARS:
        full_text = full_text[:_MAX_TEXT_CHARS] + (
            f"\n\n[Truncated — first {_MAX_TEXT_CHARS:,} of "
            f"{len(full_text):,} total chars]"
        )

    return full_text
