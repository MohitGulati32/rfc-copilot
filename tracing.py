"""
Shared LangSmith tracing helpers.

Every node that calls an LLM (or, for search_prior_art, calls Tavily)
passes a RunnableConfig built here, so every trace in the LangSmith
dashboard is tagged consistently with which node produced it and what
state the graph was in at the time, instead of repeating the same
metadata dict construction in every node file.

Note on problem_domain: State doesn't carry a classified domain field
early in the graph, that classification only happens once TrustCall
extracts an RFCMemory in update_memory, at the very end. So nodes
before that point tag with the raw problem_statement (truncated) as
readable context instead of a proper domain label. update_memory can
pass the real problem_domain once it's been extracted.
"""

from state import State


def node_config(node_name: str, state: State, model: str | None = None, problem_domain: str | None = None) -> dict:
    problem_statement = state.get("problem_statement", "")

    metadata = {
        "node_name": node_name,
        "revision_count": state.get("revision_count", 0),
        "problem_domain": problem_domain or problem_statement[:80],
    }
    if model:
        metadata["model"] = model

    return {
        "tags": [node_name],
        "metadata": metadata,
    }