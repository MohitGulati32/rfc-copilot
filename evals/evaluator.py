"""
evaluator.py

Runs the 10-item eval dataset (evals/dataset.py) through the RFC
generator twice: once with memory disabled (empty project_profile, no
retrieved_rfcs) and once with real memory (your accumulated profile and
7 approved RFCs). Each run is scored by two evaluators and logged to
LangSmith as a separate experiment, so the dashboard shows a direct
before/after comparison.

Why a separate eval graph instead of reusing graph.py's `graph`:
The production graph pauses twice for human input (interrupt_after on
clarify_requirements and generate_rfc_draft), which works for the CLI
but can't run unattended across 20 automated invocations. The eval
graph below uses the same node functions, wired without interrupts, for
a single pass: no revision loop, and clarifying questions are left
unanswered (answers=None) consistently in both conditions, so the
comparison isolates memory's effect rather than being confounded by
different amounts of human back-and-forth.

Why memory-off doesn't touch the real store: load_project_memory and
retrieve_past_rfcs both only read from the Store, never write. The
memory-off variant swaps them for stub nodes that don't touch the store
at all. Neither eval graph includes update_memory, so no eval run, in
either condition, ever writes to your real project_profile or RFC
history in local_store.json.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langsmith.evaluation import evaluate
from pydantic import BaseModel, Field

from state import State
from nodes_memory import load_project_memory, retrieve_past_rfcs
from nodes_clarify import clarify_requirements
from nodes_prior_art import search_prior_art
from nodes_generate import generate_rfc_draft
from store import store
from persistence import load_store

from evals.dataset import DATASET_NAME

load_dotenv()

REQUIRED_SECTIONS = [
    "## Problem",
    "## Proposed Solution",
    "## Alternatives Considered",
    "## Trade-offs and Risks",
    "## Implementation Plan",
    "## Open Questions",
]

judge_llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)


class RFCQualityJudgment(BaseModel):
    prior_art_referenced: bool = Field(description="Does the draft explicitly reference specific prior art or past precedent by name, rather than generic advice?")
    tradeoffs_specificity: int = Field(ge=1, le=5, description="1=generic caveats, 5=specific, well-reasoned trade-offs tied to this exact problem")
    precedent_consistency: int = Field(ge=1, le=5, description="1=ignores or contradicts any provided project context/past decisions, 5=clearly consistent with and building on them (score 3 if no relevant context was provided to begin with)")


# --- Stub nodes for the memory-disabled condition ---
# Mirror load_project_memory / retrieve_past_rfcs's return shape exactly,
# but never touch the store, so state ends up identical to a project
# with no history, without needing a second store instance.

def _no_memory_load(state: State) -> dict:
    return {"project_profile": {}}


def _no_memory_retrieve(state: State) -> dict:
    return {"retrieved_rfcs": []}


def _build_eval_graph(memory_enabled: bool):
    builder = StateGraph(State)

    builder.add_node("load_project_memory", load_project_memory if memory_enabled else _no_memory_load)
    builder.add_node("clarify_requirements", clarify_requirements)
    builder.add_node("search_prior_art", search_prior_art)
    builder.add_node("retrieve_past_rfcs", retrieve_past_rfcs if memory_enabled else _no_memory_retrieve)
    builder.add_node("generate_rfc_draft", generate_rfc_draft)

    builder.add_edge(START, "load_project_memory")
    builder.add_edge("load_project_memory", "clarify_requirements")
    builder.add_edge("clarify_requirements", "search_prior_art")
    builder.add_edge("search_prior_art", "retrieve_past_rfcs")
    builder.add_edge("retrieve_past_rfcs", "generate_rfc_draft")
    builder.add_edge("generate_rfc_draft", END)

    # No checkpointer needed, each eval item is a single, self-contained
    # pass with no pause/resume.
    return builder.compile()


_eval_graph_memory_off = _build_eval_graph(memory_enabled=False)
_eval_graph_memory_on = _build_eval_graph(memory_enabled=True)


def _run_eval_graph(graph, inputs: dict) -> dict:
    initial_state = {
        "problem_statement": inputs["problem_statement"],
        "clarifications": [],
        "prior_art": [],
        "rfc_draft": "",
        "revision_count": 0,
        "max_revisions": 3,
        "human_feedback": "",
        "approved": False,
        "project_profile": {},
        "retrieved_rfcs": [],
    }
    result = graph.invoke(initial_state)
    return {"rfc_draft": result.get("rfc_draft", "")}


def target_memory_off(inputs: dict) -> dict:
    return _run_eval_graph(_eval_graph_memory_off, inputs)


def target_memory_on(inputs: dict) -> dict:
    return _run_eval_graph(_eval_graph_memory_on, inputs)


# --- Evaluators ---

def structural_completeness(run, example) -> dict:
    """Deterministic: what fraction of the 6 required sections are present."""
    draft = (run.outputs or {}).get("rfc_draft", "")
    present = sum(1 for section in REQUIRED_SECTIONS if section in draft)
    score = present / len(REQUIRED_SECTIONS)
    return {
        "key": "structural_completeness",
        "score": score,
        "comment": f"{present}/{len(REQUIRED_SECTIONS)} required sections present",
    }


def rfc_quality_judge(run, example) -> dict:
    """
    LLM-as-judge: scores prior-art referencing, trade-off specificity,
    and precedent consistency. Returns three separate metrics in one
    call rather than three separate judge calls, cheaper and the model
    reasons about all three together with the same context.
    """
    draft = (run.outputs or {}).get("rfc_draft", "")
    relevant_prior_art = (example.outputs or {}).get("relevant_prior_art", [])

    judge = judge_llm.with_structured_output(RFCQualityJudgment)
    judgment: RFCQualityJudgment = judge.invoke(
        f"""Evaluate this RFC draft.

Prior art/precedent that would have been relevant if this team has worked on
related problems before: {relevant_prior_art}

RFC draft:
{draft}"""
    )

    return {
        "results": [
            {"key": "prior_art_referenced", "score": 1 if judgment.prior_art_referenced else 0},
            {"key": "tradeoffs_specificity", "score": judgment.tradeoffs_specificity},
            {"key": "precedent_consistency", "score": judgment.precedent_consistency},
        ]
    }


def run_baseline():
    """Day 5: memory-disabled pass across all 10 items."""
    return evaluate(
        target_memory_off,
        data=DATASET_NAME,
        evaluators=[structural_completeness, rfc_quality_judge],
        experiment_prefix="baseline-no-memory",
        description="Memory disabled: empty project_profile, no retrieved_rfcs.",
        max_concurrency=4,
    )


def run_memory_enabled():
    """Day 6: memory-enabled pass, using your real accumulated store."""
    load_store(store)
    return evaluate(
        target_memory_on,
        data=DATASET_NAME,
        evaluators=[structural_completeness, rfc_quality_judge],
        experiment_prefix="memory-enabled",
        description="Memory enabled: real project_profile and retrieved_rfcs from local_store.json.",
        max_concurrency=4,
    )


if __name__ == "__main__":
    print("Running baseline (memory disabled) eval across 10 items...")
    results = run_baseline()
    print("Baseline eval complete. Check the LangSmith dashboard under Datasets & Experiments.")
