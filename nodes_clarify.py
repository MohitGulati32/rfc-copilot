"""
clarify_requirements node.

Looks at the problem_statement and asks Claude to generate 3-5 targeted
clarifying questions, the kind a staff engineer would ask in review
before any RFC gets written. This is the first human-in-the-loop point
in the graph: it's wired with interrupt_before in graph.py, so the graph
pauses here, the human answers in chat, and clarifications get added to
state before the graph resumes.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from state import State

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3)

CLARIFY_SYSTEM_PROMPT = """You are a staff engineer reviewing a colleague's problem statement \
before they write an RFC. Your job is to identify what's missing: unstated \
constraints, scale requirements, existing systems affected, timeline pressure, \
or ambiguity in scope.

Generate 3 to 5 targeted clarifying questions. Each question should be specific \
to this problem statement, not generic boilerplate like "what is your timeline?" \
unless timeline genuinely matters here. Number the questions.

Return only the numbered questions, nothing else."""


def clarify_requirements(state: State) -> dict:
    problem_statement = state["problem_statement"]

    response = llm.invoke([
        SystemMessage(content=CLARIFY_SYSTEM_PROMPT),
        HumanMessage(content=f"Problem statement:\n\n{problem_statement}"),
    ])

    questions_text = response.content

    return {
        "messages": [response],
        # clarifications starts holding the generated questions; the human's
        # answers get appended to this same list once the graph resumes
        # after the interrupt (handled in graph.py / the CLI loop).
        "clarifications": [{"questions": questions_text, "answers": None}],
    }