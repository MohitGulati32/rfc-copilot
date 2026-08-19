"""
clarify_requirements node.

Looks at the problem_statement and asks Claude to generate 3-5 targeted
clarifying questions, the kind a staff engineer would ask in review
before any RFC gets written. This is the first human-in-the-loop point
in the graph: it's wired with interrupt_before in graph.py, so the graph
pauses here, the human answers in chat, and clarifications get added to
state before the graph resumes.

Reads project_profile from state (populated by load_project_memory,
which runs immediately before this node) so it doesn't ask about facts
memory already has. If the profile already lists a tech stack or team
size, for example, the model is told not to re-ask about those unless
something in the problem statement conflicts with what's on record.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tracing import node_config

from state import State

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3)

CLARIFY_SYSTEM_PROMPT = """You are a staff engineer reviewing a colleague's problem statement \
before they write an RFC. Your job is to identify what's missing: unstated \
constraints, scale requirements, existing systems affected, timeline pressure, \
or ambiguity in scope.

A project profile may be provided below with facts already known about this \
project (tech stack, team size, past decisions, preferred RFC style). Do not \
ask about anything the profile already answers. Only ask about it again if the \
problem statement seems to contradict the profile, in which case ask which one \
is current.

Generate 3 to 5 targeted clarifying questions. Each question should be specific \
to this problem statement, not generic boilerplate like "what is your timeline?" \
unless timeline genuinely matters here. Number the questions.

Return only the numbered questions, nothing else."""


def _format_project_profile(project_profile: dict) -> str:
    if not project_profile:
        return "No project profile available yet, nothing is known about this project."

    tech_stack = project_profile.get("tech_stack") or []
    past_decisions = project_profile.get("past_decisions") or []

    lines = [f"Project: {project_profile.get('project_name', 'unknown')}"]
    if tech_stack:
        lines.append(f"Tech stack: {', '.join(tech_stack)}")
    if project_profile.get("team_size"):
        lines.append(f"Team size: {project_profile['team_size']}")
    if past_decisions:
        lines.append("Known past decisions:\n" + "\n".join(f"- {d}" for d in past_decisions))
    if project_profile.get("preferred_rfc_style"):
        lines.append(f"Preferred RFC style: {project_profile['preferred_rfc_style']}")

    return "\n".join(lines) if len(lines) > 1 else "No project profile available yet, nothing is known about this project."


def clarify_requirements(state: State) -> dict:
    problem_statement = state["problem_statement"]
    project_profile = state.get("project_profile", {})

    user_content = f"""Project context (already known, do not re-ask about this):
{_format_project_profile(project_profile)}

Problem statement:
{problem_statement}"""

    response = llm.invoke(
        [
            SystemMessage(content=CLARIFY_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ],
        config=node_config("clarify_requirements", state, model="claude-sonnet-4-6"),
    )

    questions_text = response.content

    return {
        "messages": [response],
        # clarifications starts holding the generated questions; the human's
        # answers get appended to this same list once the graph resumes
        # after the interrupt (handled in graph.py / the CLI loop).
        "clarifications": [{"questions": questions_text, "answers": None}],
    }