import httpx
from bs4 import BeautifulSoup

_MAX_TEXT_CHARS = 80_000


def fetch_webpage(url: str) -> str:
    """Fetch an HTML web page and return its text content.

    Use this to read web pages like Wikipedia articles, news stories,
    reference pages, and search result links. For PDF documents, use
    `read_pdf` instead — it accepts URLs directly.

    Args:
        url: The full URL to fetch.

    Returns:
        The extracted text content (truncated if very long), or an error.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
    }

    timeout = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)

    try:
        resp = httpx.get(
            url, headers=headers, timeout=timeout, follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: Timed out fetching '{url}'."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} when fetching '{url}'."
    except Exception as e:
        return f"Error: Could not fetch '{url}' — {e}"

    content_type = resp.headers.get("content-type", "")

    # If we accidentally hit a PDF, tell the agent to use read_pdf instead
    if "application/pdf" in content_type or resp.content[:5] == b"%PDF-":
        final_url = str(resp.url)
        return (
            f"This URL points to a PDF document (final URL: {final_url}). "
            f"Use the `read_pdf` tool with this URL to read it."
        )

    try:
        text_body = resp.text
    except Exception:
        return f"Error: Could not decode response from '{url}'."

    if not text_body.strip():
        return f"Warning: Page at '{url}' returned empty content."

    soup = BeautifulSoup(text_body, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "noscript", "iframe", "svg"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find("body")
        or soup
    )
    text = main.get_text(separator="\n", strip=True)

    lines = [line for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    if not text.strip():
        return "Warning: Page fetched but no readable text was extracted."

    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS] + (
            f"\n\n[Truncated — showing first {_MAX_TEXT_CHARS:,} of "
            f"{len(text):,} total characters]"
        )

    return text
