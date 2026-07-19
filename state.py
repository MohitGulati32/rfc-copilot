"""
Core state definitions for the Engineering RFC Generator graph.

State (TypedDict): the shared state object that flows through every node
in the LangGraph graph. Each node reads whatever fields it needs and
returns a partial dict of updates, which LangGraph merges back in.

ProjectProfile / RFCMemory (Pydantic): schemas for the long-term memory
layer built in Phase 2. Defined now, alongside State, so the memory
fields don't require a state refactor later.
"""

from datetime import datetime
from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class State(TypedDict):
    # Full chat history for the session. The add_messages reducer appends
    # new messages instead of overwriting the list on each node update.
    messages: Annotated[list, add_messages]

    # The engineer's initial, possibly under-specified problem description.
    problem_statement: str

    # Answers gathered by the clarify_requirements node (Step 3).
    clarifications: list

    # Structured prior art results from the Tavily search node (Step 4).
    # Each item: {"title": str, "url": str, "summary": str}
    prior_art: list

    # The current draft of the RFC, produced and updated by the
    # generation node (Step 5) across revision cycles.
    rfc_draft: str

    # How many times the draft has been revised so far.
    revision_count: int

    # Hard cap on revision cycles before forcing the graph to END.
    max_revisions: int

    # Free-text feedback from the human reviewer, injected back into the
    # generation prompt on the next revision pass.
    human_feedback: str

    # Set to True by the human_approval_gate node once the draft is signed off.
    approved: bool

    # The project's long-term profile, loaded from the Store at session
    # start by load_project_memory (Step 9). Dict form of ProjectProfile.
    project_profile: dict

    # Past RFC memories retrieved via semantic search over the problem
    # statement, by retrieve_past_rfcs (Step 9). List of dicts shaped
    # like RFCMemory plus a similarity "score" and store "key".
    retrieved_rfcs: list


class ProjectProfile(BaseModel):
    """
    Long-term memory of a project's context, accumulated across RFC
    sessions. Updated via TrustCall in Step 10, so only fields explicitly
    mentioned in a given session get patched, everything else persists.
    """

    project_name: str = Field(description="Name of the project or team this RFC belongs to")
    tech_stack: list[str] = Field(default_factory=list, description="Languages, frameworks, and key infra in use")
    team_size: Optional[int] = Field(default=None, description="Approximate number of engineers on the team")
    past_decisions: list[str] = Field(default_factory=list, description="Short summaries of prior architectural decisions")
    preferred_rfc_style: Optional[str] = Field(default=None, description="Notes on tone, depth, or structure this team prefers")


class RFCMemory(BaseModel):
    """
    A single record representing one approved (or attempted) RFC, stored
    in the RFCMemory collection for future semantic search and reuse as
    few-shot examples in the generation prompt.
    """

    title: str = Field(description="Short title of the RFC")
    problem_domain: str = Field(description="e.g. 'microservices migration', 'database architecture'")
    proposed_solution: str = Field(description="One or two sentence summary of the accepted solution")
    approved: bool = Field(description="Whether this RFC was approved by the human reviewer")
    outcome: Optional[str] = Field(default=None, description="Filled in later once the team learns how the decision played out")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
