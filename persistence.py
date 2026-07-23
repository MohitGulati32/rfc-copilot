"""
Simple file-based persistence for the InMemoryStore.

InMemoryStore alone is lost when the Python process exits, which means
separate `python main.py` runs would never actually share memory,
making it impossible to test real cross-session persistence. This is a
lightweight stand-in for that: dump the store to a local JSON file on
exit, reload it on startup. Values are re-embedded on load via
store.put, so this doesn't try to serialize the vector index directly.

This is a testing/local-dev convenience, not the production answer,
Postgres-backed store (see README "What Is Next") is the real fix and
would make this file unnecessary.
"""

import json
import os

STORE_FILE = "local_store.json"

# Namespaces this project actually uses. Kept explicit rather than trying
# to discover namespaces dynamically, since InMemoryStore doesn't expose
# a "list all namespaces" API.
KNOWN_NAMESPACES = [
    ("default-project", "profile"),
    ("default-project", "rfc_memories"),
]


def save_store(store, path: str = STORE_FILE) -> None:
    dump = []
    for namespace in KNOWN_NAMESPACES:
        items = store.search(namespace, limit=1000)
        for item in items:
            dump.append({
                "namespace": list(item.namespace),
                "key": item.key,
                "value": item.value,
            })

    with open(path, "w") as f:
        json.dump(dump, f, indent=2, default=str)


def load_store(store, path: str = STORE_FILE) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        dump = json.load(f)

    for entry in dump:
        store.put(tuple(entry["namespace"]), entry["key"], entry["value"])
