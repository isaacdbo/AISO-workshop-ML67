import os
import tempfile
import fitz  # PyMuPDF
import httpx

_MAX_TEXT_CHARS = 500_000
_MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024


def read_pdf(source: str) -> str:
    """Read a PDF and return its full text content, page by page.

    Accepts EITHER:
    - A local file path  (e.g. "/tmp/report.pdf", "benchmark/attachments/9.pdf")
    - A URL to a PDF      (e.g. "https://example.com/report.pdf",
                           "https://doi.org/10.1353/book.24372")

    The tool automatically detects which one you provided.
    For URLs it will download the PDF first, then extract text.

    Args:
        source: A local file path or a URL pointing to a PDF.

    Returns:
        The extracted text from all pages with page separators
        (e.g. "--- Page 1 ---\\n..."), or an error message.
    """
    if source.startswith("http://") or source.startswith("https://"):
        return _read_pdf_from_url(source)
    else:
        return _read_pdf_from_file(source)


def _read_pdf_from_file(file_path: str) -> str:
    """Read a PDF from a local file path."""
    if not os.path.exists(file_path):
        return f"Error: File not found at '{file_path}'."

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return f"Error: Could not open PDF — {e}"

    return _extract_text(doc)


def _read_pdf_from_url(url: str) -> str:
    """Download a PDF from a URL, then extract its text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/octet-stream,*/*",
    }

    # Generous read timeout for large PDFs; short connect timeout
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)

    try:
        with httpx.stream(
            "GET", url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as resp:
            resp.raise_for_status()

            # Stream into a temp file to handle large PDFs without
            # holding everything in memory at once
            total = 0
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            try:
                for chunk in resp.iter_bytes(chunk_size=65_536):
                    total += len(chunk)
                    if total > _MAX_DOWNLOAD_BYTES:
                        tmp.close()
                        os.unlink(tmp.name)
                        return (
                            f"Error: PDF at '{url}' exceeds "
                            f"{_MAX_DOWNLOAD_BYTES // (1024*1024)} MB limit."
                        )
                    tmp.write(chunk)
                tmp.close()
            except Exception as e:
                tmp.close()
                os.unlink(tmp.name)
                raise e

    except httpx.TimeoutException:
        return f"Error: Timed out downloading PDF from '{url}'."
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        return f"Error: HTTP {code} when downloading '{url}'."
    except Exception as e:
        return f"Error: Could not download PDF from '{url}' — {e}"

    # Now read the temp file with PyMuPDF
    try:
        doc = fitz.open(tmp.name)
        result = _extract_text(doc)
    finally:
        os.unlink(tmp.name)

    return result


def _extract_text(doc) -> str:
    """Extract page-labelled text from an open PyMuPDF document."""
    if doc.page_count == 0:
        doc.close()
        return "Error: The PDF has no pages."

    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append(f"--- Page {i} ---\n{text}")
        else:
            pages.append(
                f"--- Page {i} ---\n[No extractable text on this page]")

    doc.close()
    full_text = "\n\n".join(pages)

    if len(full_text) > _MAX_TEXT_CHARS:
        full_text = full_text[:_MAX_TEXT_CHARS] + (
            f"\n\n[Truncated — showing first {_MAX_TEXT_CHARS:,} characters "
            f"of {len(full_text):,} total]"
        )

    return full_text
