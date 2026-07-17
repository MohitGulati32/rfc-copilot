"""
generate_rfc_draft node.

Takes problem_statement, clarifications, and prior_art from state and
asks Claude to draft a structured RFC. The prompt enforces the standard
sections: Problem, Proposed Solution, Alternatives Considered,
Trade-offs and Risks, Implementation Plan, Open Questions.

This node is also the target of the revision loop (Step 6): when
human_feedback is present in state, it gets injected into the prompt so
the next draft addresses it directly, and revision_count is incremented
here on every pass.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from state import State

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.4)

RFC_SYSTEM_PROMPT = """You are a senior engineer writing an RFC for your team. Produce a \
clear, well-structured RFC using exactly these six sections, in this order:

## Problem
## Proposed Solution
## Alternatives Considered
## Trade-offs and Risks
## Implementation Plan
## Open Questions

Guidelines:
- Ground the Proposed Solution and Alternatives Considered sections in the prior art \
provided, reference specific approaches by name where relevant.
- Alternatives Considered should include at least two real alternatives with honest \
reasons they were not chosen, not strawmen.
- Trade-offs and Risks should be specific to this problem, not generic caveats.
- Keep the tone direct and technical, written for a senior engineering audience that \
will push back on hand-waving.
- If human feedback on a previous draft is provided, address it explicitly rather \
than making cosmetic changes."""


def _format_prior_art(prior_art: list) -> str:
    if not prior_art:
        return "No prior art was found."
    lines = []
    for item in prior_art:
        lines.append(f"- {item.get('title', 'Untitled')} ({item.get('url', '')}): {item.get('summary', '')}")
    return "\n".join(lines)


def _format_clarifications(clarifications: list) -> str:
    if not clarifications:
        return "No clarifying questions were asked."
    lines = []
    for qa_round in clarifications:
        lines.append(f"Questions:\n{qa_round.get('questions', '')}")
        if qa_round.get("answers"):
            lines.append(f"Answers:\n{qa_round.get('answers')}")
    return "\n\n".join(lines)


def generate_rfc_draft(state: State) -> dict:
    problem_statement = state["problem_statement"]
    clarifications = state.get("clarifications", [])
    prior_art = state.get("prior_art", [])
    human_feedback = state.get("human_feedback", "")
    revision_count = state.get("revision_count", 0)

    user_content = f"""Problem statement:
{problem_statement}

Clarifying questions and answers:
{_format_clarifications(clarifications)}

Prior art found:
{_format_prior_art(prior_art)}"""

    if human_feedback:
        user_content += f"""

This is a revision. Here is the previous draft and the human feedback on it, \
address the feedback directly in this new draft:

Previous draft:
{state.get('rfc_draft', '')}

Feedback:
{human_feedback}"""

    response = llm.invoke([
        SystemMessage(content=RFC_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    return {
        "messages": [response],
        "rfc_draft": response.content,
        "revision_count": revision_count + 1,
    }
