"""
The full Phase 1 + Phase 2 graph:

load_project_memory -> clarify_requirements -> search_prior_art
-> retrieve_past_rfcs -> generate_rfc_draft -> (loop back to
generate_rfc_draft, or END).

Two human-in-the-loop pause points:
1. interrupt_after clarify_requirements: the node has generated its
   questions and they're sitting in state, the human answers before
   search_prior_art runs.
2. interrupt_after generate_rfc_draft: a draft exists, the human
   approves or gives feedback before route_after_generation decides
   whether to loop back or end.

Memory is read-only in this graph: load_project_memory and
retrieve_past_rfcs pull from the Store to inform generation, they don't
write to it. Writing happens in Step 10's update_memory node, wired in
separately once a draft is actually approved.
"""

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import State
from nodes_memory import load_project_memory, retrieve_past_rfcs
from nodes_clarify import clarify_requirements
from nodes_prior_art import search_prior_art
from nodes_generate import generate_rfc_draft
from routing import route_after_generation


def build_graph():
    builder = StateGraph(State)

    builder.add_node("load_project_memory", load_project_memory)
    builder.add_node("clarify_requirements", clarify_requirements)
    builder.add_node("search_prior_art", search_prior_art)
    builder.add_node("retrieve_past_rfcs", retrieve_past_rfcs)
    builder.add_node("generate_rfc_draft", generate_rfc_draft)

    builder.add_edge(START, "load_project_memory")
    builder.add_edge("load_project_memory", "clarify_requirements")
    builder.add_edge("clarify_requirements", "search_prior_art")
    builder.add_edge("search_prior_art", "retrieve_past_rfcs")
    builder.add_edge("retrieve_past_rfcs", "generate_rfc_draft")
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
