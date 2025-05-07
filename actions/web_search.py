from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from engine.net import get


def web_search(user_input: str, query: str) -> str:
    if not query.strip():
        return "❌ I need something to search for."

    encoded_query = quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        res = get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        results = soup.select(".result__snippet")

        if not results:
            return "🔍 I searched, but couldn’t find anything useful."

        top_snippets = [r.text.strip() for r in results[:3] if r.text.strip()]
        summary = "\n".join(f"- {snippet}" for snippet in top_snippets)
        return f"🔎 Here’s what I found about '{query}':\n{summary}"

    except Exception as e:
        return f"⚠️ Web search failed: {e}"
