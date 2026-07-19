"""
Memory nodes: load_project_memory and retrieve_past_rfcs.

Both read from the Store (Step 8), they don't write to it, writing
happens later in Step 10's update_memory node via TrustCall, once a
draft has actually been approved.

Namespacing: everything lives under a single "default-project"
namespace for now, since this is a single-user CLI tool. A real
multi-project version would derive the namespace from a project ID
passed in at session start, the store and node logic here don't need to
change for that, just the namespace construction.
"""

from dotenv import load_dotenv

from state import ProjectProfile, State
from store import store

load_dotenv()

PROJECT_NAMESPACE = ("default-project", "profile")
PROJECT_PROFILE_KEY = "profile"
RFC_NAMESPACE = ("default-project", "rfc_memories")


def load_project_memory(state: State) -> dict:
    item = store.get(PROJECT_NAMESPACE, PROJECT_PROFILE_KEY)

    if item is None:
        # First time this project has been seen, start with an empty
        # profile rather than failing. update_memory (Step 10) will
        # populate it once the first RFC is approved.
        profile = ProjectProfile(project_name="default-project").model_dump(mode="json")
    else:
        profile = item.value

    return {"project_profile": profile}


def retrieve_past_rfcs(state: State) -> dict:
    problem_statement = state["problem_statement"]

    results = store.search(RFC_NAMESPACE, query=problem_statement, limit=3)

    retrieved = []
    for r in results:
        retrieved.append({
            "key": r.key,
            "score": r.score,
            **r.value,
        })

    return {"retrieved_rfcs": retrieved}
