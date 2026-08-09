"""
vector_store.py
Builds and queries the ChromaDB collection for the interview question bank.

This is the RAG retrieval layer consumed by the Question Generator Agent.
Metadata (company/topic/difficulty/question_type/year) is stored alongside
each embedded question so retrieval can be filtered, not just semantic.
"""

import json
from pathlib import Path
import chromadb
from chromadb.config import Settings

from embeddings import get_embedding_function

DATA_PATH = Path(__file__).parent.parent / "data" / "questions_clean.json"
PERSIST_DIR = Path(__file__).parent.parent / "data" / "chroma_store"
COLLECTION_NAME = "interview_questions"


def get_client():
    return chromadb.PersistentClient(path=str(PERSIST_DIR))


def build_collection(reset: bool = False):
    """Loads questions_clean.json, embeds it, and stores it in ChromaDB."""
    questions = json.loads(DATA_PATH.read_text())

    client = get_client()
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    ids = [q["id"] for q in questions]
    documents = [q["search_text"] for q in questions]
    metadatas = []
    for q in questions:
        metadatas.append(
            {
                "company": q["company"],
                "role": q["role"],
                "topic": q["topic"],
                "difficulty": q["difficulty"],
                "question_type": q["question_type"],
                "tags": ",".join(q["tags"]),  # chroma metadata must be scalar
                "year": q["year"] if q["year"] is not None else -1,
                "question_text": q["question_text"],
            }
        )

    # Chroma upsert in batches (keeps memory bounded for larger banks later)
    batch_size = 200
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    print(f"Indexed {collection.count()} questions into collection '{COLLECTION_NAME}'")
    return collection


def get_collection():
    client = get_client()
    return client.get_collection(
        name=COLLECTION_NAME, embedding_function=get_embedding_function()
    )


def query_questions(
    query_text: str,
    n_results: int = 5,
    company: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    exclude_ids: list[str] | None = None,
):
    """
    Retrieves candidate seed questions for the Question Generator Agent.
    Combines semantic search with metadata filtering (company/topic/etc).
    """
    collection = get_collection()

    where_clauses = []
    if company:
        where_clauses.append({"company": company})
    if topic:
        where_clauses.append({"topic": topic})
    if difficulty:
        where_clauses.append({"difficulty": difficulty})
    if question_type:
        where_clauses.append({"question_type": question_type})

    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    result = collection.query(
        query_texts=[query_text],
        n_results=n_results * 3 if exclude_ids else n_results,  # over-fetch to allow filtering
        where=where,
    )

    hits = []
    for i in range(len(result["ids"][0])):
        qid = result["ids"][0][i]
        if exclude_ids and qid in exclude_ids:
            continue
        hits.append(
            {
                "id": qid,
                "question_text": result["metadatas"][0][i]["question_text"],
                "company": result["metadatas"][0][i]["company"],
                "topic": result["metadatas"][0][i]["topic"],
                "difficulty": result["metadatas"][0][i]["difficulty"],
                "question_type": result["metadatas"][0][i]["question_type"],
                "tags": result["metadatas"][0][i]["tags"].split(",") if result["metadatas"][0][i]["tags"] else [],
                "distance": result["distances"][0][i],
            }
        )
        if len(hits) >= n_results:
            break

    return hits


if __name__ == "__main__":
    build_collection(reset=True)
