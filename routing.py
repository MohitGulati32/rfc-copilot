"""
Revision loop routing logic.

This is the conditional edge that sits after generate_rfc_draft. The
generation node itself pauses via interrupt_after (wired in graph.py),
so by the time this function runs, a human has already reviewed the
draft and updated state with either approved=True or human_feedback
containing their notes.

route_after_generation decides where the graph goes next:
- approved -> update_memory (which then routes to END)
- not approved, revisions remaining -> back to generate_rfc_draft
- not approved, max_revisions hit -> END directly, no memory write.
  An unapproved draft that just ran out of revisions isn't precedent
  worth remembering, so it's deliberately excluded from memory.
"""

from langgraph.graph import END

from state import State


def route_after_generation(state: State) -> str:
    if state.get("approved"):
        return "update_memory"

    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)

    if revision_count >= max_revisions:
        return END

    return "generate_rfc_draft"
