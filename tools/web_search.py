from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from engine.net import get

name = "web_search"
description = "Searches the web using DuckDuckGo and returns top snippets."
pattern = r"(?:search|google|look up|find|can you search(?: for me)?)(?: about| for)?\s+(?P<query>[A-Za-z0-9 '\-]+)[\?\. ]*$"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; Suhana/1.0; +https://github.com/reterics/suhana)"
}

def duckduckgo(query: str) -> list[str]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    res = get(url, timeout=10, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    results = soup.select(".result__snippet")
    return [r.text.strip() for r in results if r.text.strip()]

def bing(query: str) -> list[str]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    res = get(url, timeout=10, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    results = soup.select("li.b_algo h2 + p")  # or ".b_caption p"
    return [r.text.strip() for r in results if r.text.strip()]

def brave(query: str) -> list[str]:
    url = f"https://search.brave.com/search?q={quote_plus(query)}"
    res = get(url, timeout=10, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    results = soup.select(".snippet-description")
    return [r.text.strip() for r in results if r.text.strip()]

def action(user_input: str, query: str, engine: str = "duckduckgo") -> str:
    if not query.strip():
        return "I need something to search for."

    try:
        provider = {
            "duckduckgo": duckduckgo,
            "bing": bing,
            "brave": brave,
        }.get(engine.lower(), duckduckgo)

        snippets = provider(query)

        if not snippets:
            return "I searched, but couldn’t find anything useful."

        summary = "\n".join(f"- {s}" for s in snippets[:3])
        return f"Here’s what I found about '{query}':\n{summary}"

    except Exception as e:
        return f"Web search failed: {e}"
