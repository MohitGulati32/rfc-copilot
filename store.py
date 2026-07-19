"""
LangGraph Store setup for the long-term memory layer.

InMemoryStore is fine for local development and this portfolio project,
it holds everything in process memory and is lost on restart. A
Postgres-backed store is the natural swap for production use (see
README "What Is Next"), the store interface stays the same either way.

Semantic search is powered by Voyage AI's voyage-4-lite model (1024
dimensions by default), so memories can be retrieved by meaning, not
just exact key lookup, this is what lets Step 9 pull relevant past RFCs
and project context even when the new problem statement is worded
differently from anything stored before.
"""

from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langgraph.store.memory import InMemoryStore

load_dotenv()

embeddings = VoyageAIEmbeddings(model="voyage-4-lite")

store = InMemoryStore(
    index={
        "embed": embeddings,
        "dims": 1024,
        # which fields inside a stored item get embedded for semantic
        # search, both ProjectProfile and RFCMemory records will store
        # their searchable content under a "text" key when we write them
        # in Step 9.
        "fields": ["text"],
    }
)
