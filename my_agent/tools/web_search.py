import time
from duckduckgo_search import DDGS


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a list of results with titles, URLs, and snippets.

    Use this tool to find real-world facts, current information, publications,
    or any verifiable claim. After reviewing the snippets, call `fetch_webpage`
    on the most relevant URL to read the full content.

    Tips for effective queries:
    - Keep queries short and keyword-focused: "BERT paper 2018 layers" not
      "how many layers does the BERT model have".
    - For academic work, search by DOI, title, or key phrases.
    - For people/events, include distinguishing details.
    - If the first query fails, try simpler or alternative wording.

    Args:
        query: A concise search query (ideally 2-6 keywords).
        max_results: Number of results to return (1-10). Default is 5.

    Returns:
        A numbered list of results (title, URL, snippet), or an error message.
    """
    max_results = max(1, min(10, max_results))

    # Try multiple backends — DuckDuckGo's default API can be flaky
    errors = []
    results = []
    for backend in ("api", "lite", "html"):
        try:
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(query, max_results=max_results, backend=backend)
                )
            if results:
                break
        except Exception as e:
            errors.append(f"{backend}: {e}")
            time.sleep(1)

    if not results:
        if errors:
            return (
                f"Error: All search backends failed for '{query}'.\n"
                + "\n".join(errors)
                + "\nTry a simpler or rephrased query."
            )
        return f"No results found for '{query}'. Try different keywords."

    formatted = []
    for i, r in enumerate(results, start=1):
        title = r.get("title", "No title")
        url = r.get("href", "No URL")
        snippet = r.get("body", "No snippet")
        formatted.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}")

    return "\n\n".join(formatted)
