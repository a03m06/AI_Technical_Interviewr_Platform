"""
eval_store.py
Second ChromaDB collection: canonical concept explanations, used to ground
the Evaluation Agent's scoring. Separate from the question bank collection
in vector_store.py because it's a different kind of document (explanation,
not a question) and is queried differently (by concept, not by
company/difficulty).

get_evaluation_context() is the single entry point the Evaluation Agent
node should call: given the question just asked, it returns both the
retrieved canonical explanation(s) and the correct rubric to score against.
"""

import json
from pathlib import Path
import chromadb

from embeddings import get_embedding_function

DATA_PATH = Path(__file__).parent.parent / "data" / "canonical_explanations.json"
RUBRICS_PATH = Path(__file__).parent.parent / "data" / "rubrics.json"
PERSIST_DIR = Path(__file__).parent.parent / "data" / "chroma_store"
COLLECTION_NAME = "canonical_explanations"


def get_client():
    return chromadb.PersistentClient(path=str(PERSIST_DIR))


def build_eval_collection(reset: bool = False):
    entries = json.loads(DATA_PATH.read_text())

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

    ids, documents, metadatas = [], [], []
    for e in entries:
        ids.append(e["id"])
        # embed concept + explanation + key points together for richer retrieval signal
        doc_text = e["concept"] + " | " + e["explanation"] + " | " + " ".join(e["key_points"])
        documents.append(doc_text)
        metadatas.append(
            {
                "topic": e["topic"],
                "tags": ",".join(e["tags"]),
                "concept": e["concept"],
                # store the full entry as JSON so we can return it whole on retrieval
                "full_entry": json.dumps(e),
            }
        )

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indexed {collection.count()} canonical explanations into '{COLLECTION_NAME}'")
    return collection


def get_eval_collection():
    client = get_client()
    return client.get_collection(name=COLLECTION_NAME, embedding_function=get_embedding_function())


def query_canonical_explanations(query_text: str, topic: str | None = None, n_results: int = 2):
    """Retrieves the most relevant canonical explanation(s) for grounding evaluation."""
    collection = get_eval_collection()
    where = {"topic": topic} if topic else None

    result = collection.query(query_texts=[query_text], n_results=n_results, where=where)

    hits = []
    for i in range(len(result["ids"][0])):
        entry = json.loads(result["metadatas"][0][i]["full_entry"])
        entry["distance"] = result["distances"][0][i]
        hits.append(entry)
    return hits


# The question bank uses ~75 granular topic labels (e.g. "Array", "Tree",
# "Dynamic Programming", "High-Level Design", "PEFT", "Hugging Face"...),
# while the canonical explanation corpus is authored at a broader topic
# grain (e.g. "DSA", "System Design", "LLM"). This maps the former to the
# latter so topic-filtered retrieval actually hits instead of silently
# falling through to an unfiltered search every time.
TOPIC_GROUP_MAP = {
    # DSA family
    "Array": "DSA", "Tree": "DSA", "Dynamic Programming": "DSA",
    # OOP family
    "OOD": "OOP",
    # LLD family
    "Low-Level Design": "LLD",
    # System design family
    "HLD": "System Design", "High-Level Design": "System Design",
    # Machine learning family
    "Data Science": "Machine Learning", "Data Analysis": "Machine Learning",
    "Data Engineering": "Machine Learning", "Data Visualization": "Machine Learning",
    "Deep Learning": "Machine Learning", "Computer Vision": "Machine Learning",
    "Natural Language Processing": "Machine Learning", "Model Architectures": "Machine Learning",
    "Model Optimization": "Machine Learning", "Model Deployment and Monitoring": "Machine Learning",
    "Autoencoders": "Machine Learning", "GANs": "Machine Learning", "VAE": "Machine Learning",
    "Diffusion Models": "Machine Learning", "Evaluation": "Machine Learning",
    # Generative AI / agentic / safety family
    "AI": "Generative AI", "Artificial Intelligence": "Generative AI",
    "AI Ethics & Bias": "Generative AI", "Agentic AI": "Generative AI",
    "Alignment": "Generative AI", "Generative AI Fundamentals": "Generative AI",
    "Generative Models": "Generative AI", "Hallucinations": "Generative AI",
    "Prompt Engineering": "Generative AI", "Prompt Injection and Security": "Generative AI",
    "Safety": "Generative AI", "Multi-Agent Systems": "Generative AI",
    "Multimodal": "Generative AI", "Interoperability": "Generative AI",
    "Reliability & Failure Handling": "Generative AI", "Compliance & Auditability": "Generative AI",
    "Build vs Buy": "Generative AI", "Future-Proofing": "Generative AI",
    "Inference Latency Optimization": "Generative AI", "Inference Observability and Fallbacks": "Generative AI",
    "Scaling": "Generative AI",
    # LLM internals family
    "LLMs": "LLM", "Transformers": "LLM", "Attention Mechanisms": "LLM",
    "Tokenization": "LLM", "Fine-tuning": "LLM", "PEFT": "LLM",
    "Hugging Face": "LLM", "Context and Memory Management": "LLM", "Memory": "LLM",
    "Embeddings": "LLM",
    # RAG family
    "Retrieval-Augmented Generation (RAG)": "RAG", "Vector Databases": "RAG",
    # Frontend/JS family -- no dedicated canonical entries yet, route to JavaScript
    "React": "JavaScript", "Node.js": "JavaScript", "Frameworks": "JavaScript",
}


def resolve_topic_group(raw_topic: str) -> str:
    """Maps a question bank topic to the broader canonical-explanation topic bucket."""
    return TOPIC_GROUP_MAP.get(raw_topic, raw_topic)


def get_rubric(question_type: str) -> dict:
    """Loads the scoring rubric for a given question_type. Falls back to Theory if unmapped."""
    rubrics = json.loads(RUBRICS_PATH.read_text())
    return rubrics.get(question_type, rubrics["Theory"])


def get_evaluation_context(question_text: str, topic: str, question_type: str) -> dict:
    """
    Single entry point for the Evaluation Agent node.
    Returns everything needed to ground and structure a scoring call:
    - rubric: the criteria/weights to score against
    - grounding: retrieved canonical explanation(s) relevant to this question
    """
    resolved_topic = resolve_topic_group(topic)
    grounding = query_canonical_explanations(question_text, topic=resolved_topic, n_results=2)
    if not grounding:
        # topic filter found nothing (e.g. a niche topic with no authored entry yet) -- retry without filter
        grounding = query_canonical_explanations(question_text, topic=None, n_results=2)

    rubric = get_rubric(question_type)

    return {
        "rubric": rubric,
        "grounding": grounding,
    }


if __name__ == "__main__":
    build_eval_collection(reset=True)
