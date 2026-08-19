"""
search_prior_art node.

Uses Tavily to search for industry best practices, public RFCs, and
architectural patterns relevant to the problem statement and the
clarifying questions gathered in Step 3. Results are parsed into a
structured list so later nodes (and the generation prompt) can cite
specific sources instead of vague hand-waving.
"""

from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from tracing import node_config
from state import State

load_dotenv()

tavily_search = TavilySearch(max_results=5, search_depth="advanced")


MAX_QUERY_LENGTH = 400


def _build_query(state: State) -> str:
    problem_statement = state["problem_statement"]
    clarifications = state.get("clarifications", [])

    # Fold the most recent round of clarifying Q&A into the query so the
    # search reflects the narrowed-down problem, not just the original
    # one-line statement. Tavily caps queries at 400 characters, so the
    # problem statement always takes priority and any remaining budget
    # goes to the clarifying answers.
    query = problem_statement
    if clarifications:
        latest = clarifications[-1]
        answers = latest.get("answers")
        if answers:
            remaining = MAX_QUERY_LENGTH - len(query) - 1
            if remaining > 20:
                query = f"{query} {str(answers)[:remaining]}"

    return query[:MAX_QUERY_LENGTH].strip()


def search_prior_art(state: State) -> dict:
    query = _build_query(state)

    response = tavily_search.invoke(
        {"query": query},
        config=node_config("search_prior_art", state),
    )

    # TavilySearch swallows exceptions internally (auth errors, network
    # issues) and returns {"error": ...} instead of raising. Surface that
    # loudly rather than silently returning an empty prior_art list, which
    # looks identical to a legitimate "no results found" case.
    if "error" in response:
        raise RuntimeError(f"Tavily search failed: {response['error']}")

    raw_results = response.get("results", [])

    prior_art = []
    for item in raw_results:
        prior_art.append({
            "title": item.get("title", "Untitled"),
            "url": item.get("url", ""),
            # Tavily's "content" field is the relevant excerpt; trim it down
            # to keep the generation prompt lean, a full one-sentence
            # summary gets produced later by the generation node itself.
            "summary": (item.get("content", "") or "")[:280].strip(),
        })

    return {"prior_art": prior_art}
