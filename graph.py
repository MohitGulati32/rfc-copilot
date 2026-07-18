"""
The full Phase 1 graph: clarify_requirements -> search_prior_art ->
generate_rfc_draft -> (loop back to generate_rfc_draft, or END).

Two human-in-the-loop pause points:
1. interrupt_after clarify_requirements: the node has generated its
   questions and they're sitting in state, the human answers before
   search_prior_art runs.
2. interrupt_after generate_rfc_draft: a draft exists, the human
   approves or gives feedback before route_after_generation decides
   whether to loop back or end.

No memory layer yet, that's Phase 2. This is the working end-to-end
flow from Phase 1.
"""

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import State
from nodes_clarify import clarify_requirements
from nodes_prior_art import search_prior_art
from nodes_generate import generate_rfc_draft
from routing import route_after_generation


def build_graph():
    builder = StateGraph(State)

    builder.add_node("clarify_requirements", clarify_requirements)
    builder.add_node("search_prior_art", search_prior_art)
    builder.add_node("generate_rfc_draft", generate_rfc_draft)

    builder.add_edge(START, "clarify_requirements")
    builder.add_edge("clarify_requirements", "search_prior_art")
    builder.add_edge("search_prior_art", "generate_rfc_draft")
    builder.add_conditional_edges(
        "generate_rfc_draft",
        route_after_generation,
        {"generate_rfc_draft": "generate_rfc_draft", END: END},
    )

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_after=["clarify_requirements", "generate_rfc_draft"],
    )


graph = build_graph()
