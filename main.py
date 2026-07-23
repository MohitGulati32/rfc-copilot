"""
Interactive CLI for the Engineering RFC Generator.

Run: python main.py

Walks through: problem statement -> clarifying questions (you answer) ->
prior art search -> RFC draft -> your review (approve or give feedback,
looping up to max_revisions times) -> final draft printed to screen.

Memory persists across runs via persistence.py, which loads local_store.json
at startup and saves back to it when the session ends (whether it ends
normally or you Ctrl+C out), so a later `python main.py` run can actually
build on what an earlier run learned.
"""

from graph import graph
from store import store
from persistence import load_store, save_store


def main():
    load_store(store)

    print("=" * 60)
    print("Engineering RFC Generator")
    print("=" * 60)

    try:
        run_session()
    finally:
        save_store(store)


def run_session():
    problem_statement = input("\nDescribe the problem you need an RFC for:\n> ").strip()

    config = {"configurable": {"thread_id": "cli-session"}}
    initial_state = {
        "problem_statement": problem_statement,
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

    graph.invoke(initial_state, config)

    while True:
        state = graph.get_state(config)
        next_nodes = state.next

        if not next_nodes:
            break

        if next_nodes == ("search_prior_art",):
            # clarify_requirements just ran, questions are in state
            latest = state.values["clarifications"][-1]
            print("\n" + "-" * 60)
            print("Clarifying questions:")
            print("-" * 60)
            print(latest["questions"])
            answers = input("\nYour answers (one message, any format):\n> ").strip()

            updated = state.values["clarifications"]
            updated[-1]["answers"] = answers
            graph.update_state(config, {"clarifications": updated})
            graph.invoke(None, config)

        elif next_nodes == ("generate_rfc_draft",):
            # generate_rfc_draft just ran, a draft is in state
            print("\n" + "-" * 60)
            print(f"Draft (revision {state.values['revision_count']}):")
            print("-" * 60)
            print(state.values["rfc_draft"])

            if state.values["revision_count"] >= state.values["max_revisions"]:
                print(f"\nMax revisions ({state.values['max_revisions']}) reached, shipping as-is.")
                break

            decision = input("\nApprove this draft? (y/n)\n> ").strip().lower()

            if decision.startswith("y"):
                graph.update_state(config, {"approved": True})
            else:
                feedback = input("\nWhat should change in the next revision?\n> ").strip()
                graph.update_state(config, {"human_feedback": feedback, "approved": False})

            graph.invoke(None, config)

        else:
            # Unexpected pause point, resume anyway rather than hanging
            graph.invoke(None, config)

    final_state = graph.get_state(config)
    print("\n" + "=" * 60)
    print("FINAL RFC")
    print("=" * 60)
    print(final_state.values.get("rfc_draft", ""))


if __name__ == "__main__":
    main()
