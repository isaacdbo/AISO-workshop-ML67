import fitz


def read_pdf(file_path: str) -> str:
    """Read a PDF file and return its full text content.

    ALWAYS use this tool when a question references a PDF file or attachment.
    Pass the exact file path as provided in the question or context.

    The tool extracts all readable text from every page of the PDF,
    preserving the page order. Each page is labelled so you can
    reference specific pages in your answer.

    Args:
        file_path: The absolute or relative path to the PDF file
                   (e.g. "/tmp/library_catalog.pdf").

    Returns:
        The extracted text from all pages, with page separators,
        or an error message if the file cannot be read.
    """
    try:
        doc = fitz.open(file_path)
    except FileNotFoundError:
        return f"Error: File not found at '{file_path}'."
    except Exception as e:
        return f"Error: Could not open PDF — {e}"

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

    # Guard against enormous PDFs blowing up the context window
    max_chars = 100_000
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + (
            f"\n\n[Truncated — showing first {max_chars:,} characters "
            f"of {len(full_text):,} total]"
        )

    return full_text
