"""
update_memory node.

Runs only when a draft has actually been approved (wired via routing.py
so it's skipped entirely if the loop ends by hitting max_revisions
without approval, we don't want unapproved drafts polluting memory).

Two writes happen here:
1. ProjectProfile is patched, not overwritten, via TrustCall. TrustCall
   generates a JSON patch against the existing profile, so fields the
   session didn't touch are left exactly as they were, only genuinely
   new or corrected information gets written.
2. A fresh RFCMemory record is created for this specific RFC and stored
   with a "text" field so it's searchable by retrieve_past_rfcs in
   future sessions.
"""

import uuid

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from trustcall import create_extractor
from tracing import node_config
from state import ProjectProfile, RFCMemory, State
from store import store
from nodes_memory import PROJECT_NAMESPACE, PROJECT_PROFILE_KEY, RFC_NAMESPACE

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

profile_extractor = create_extractor(llm, tools=[ProjectProfile], tool_choice="ProjectProfile")
rfc_memory_extractor = create_extractor(llm, tools=[RFCMemory], tool_choice="RFCMemory")


def _format_clarifications(clarifications: list) -> str:
    if not clarifications:
        return "No clarifying questions were asked."
    lines = []
    for qa_round in clarifications:
        lines.append(f"Questions:\n{qa_round.get('questions', '')}")
        if qa_round.get("answers"):
            lines.append(f"Answers:\n{qa_round.get('answers')}")
    return "\n\n".join(lines)


def update_memory(state: State) -> dict:
    if not state.get("approved"):
        # Shouldn't be reached given the routing, but guard anyway rather
        # than silently writing memory for an unapproved draft.
        return {}

    problem_statement = state["problem_statement"]
    clarifications = state.get("clarifications", [])
    rfc_draft = state.get("rfc_draft", "")
    existing_profile = state.get("project_profile", {})

    session_summary = f"""Problem statement:
{problem_statement}

Clarifying questions and answers:
{_format_clarifications(clarifications)}

Approved RFC draft:
{rfc_draft}"""

    # 1. Patch the ProjectProfile with anything new this session revealed.
    profile_result = profile_extractor.invoke(
        {
            "messages": [
                ("system", "Update the project profile based on this RFC session. Only "
                           "change fields where the session revealed genuinely new or "
                           "corrected information (tech stack mentioned, team size "
                           "mentioned, a new past decision worth remembering, a style "
                           "preference expressed). Leave everything else exactly as-is."),  # unchanged
                ("human", session_summary),
            ],
            "existing": {"ProjectProfile": existing_profile} if existing_profile else None,
        },
        config=node_config("update_memory_profile", state, model="claude-sonnet-4-6"),
    )
    updated_profile: ProjectProfile = profile_result["responses"][0]
    updated_profile_dict = updated_profile.model_dump(mode="json")
    store.put(PROJECT_NAMESPACE, PROJECT_PROFILE_KEY, updated_profile_dict)

    # 2. Create a new RFCMemory record for this approved RFC.
    rfc_result = rfc_memory_extractor.invoke(
        {
            "messages": [
                ("system", "Summarize this approved RFC into the RFCMemory schema. "
                           "The proposed_solution should be one or two sentences, "
                           "specific enough to be useful as precedent for a future, "
                           "related RFC. approved should be true."),  # unchanged
                ("human", session_summary),
            ],
        },
        config=node_config("update_memory_rfc_record", state, model="claude-sonnet-4-6"),
    )
    new_rfc_memory: RFCMemory = rfc_result["responses"][0]
    new_rfc_memory_dict = new_rfc_memory.model_dump(mode="json")

    rfc_key = f"rfc-{uuid.uuid4().hex[:8]}"
    store.put(RFC_NAMESPACE, rfc_key, {
        "text": f"{new_rfc_memory.title}: {new_rfc_memory.proposed_solution}",
        **new_rfc_memory_dict,
    })

    return {"project_profile": updated_profile_dict}
