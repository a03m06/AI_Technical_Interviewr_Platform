"""
embeddings.py
Provides the embedding function used by the vector store.

- OpenAIEmbeddingFunction: used in production. Requires OPENAI_API_KEY env var.
  Uses text-embedding-3-small (cheap, 1536-dim, good quality for this use case).
- LocalDevEmbeddingFunction: a deterministic, dependency-light fallback used
  ONLY when no OPENAI_API_KEY is set. It hashes n-grams into a fixed-size
  vector (a simplified feature-hashing / bag-of-words embedding). It is NOT
  semantically meaningful the way a real embedding model is -- it exists so
  the ingestion/retrieval pipeline can be built and tested end-to-end without
  hitting a network API. Swap to OpenAIEmbeddingFunction for real use.
"""

import os
import re
import hashlib
import math
from chromadb import Documents, EmbeddingFunction, Embeddings

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_DEV_DIM = 384


class OpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model: str = OPENAI_EMBEDDING_MODEL, api_key: str | None = None):
        from openai import OpenAI
        self.model = model
        self.client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def __call__(self, input: Documents) -> Embeddings:
        # OpenAI API accepts batches directly; chunk defensively for very large batches
        out: Embeddings = []
        batch_size = 100
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            out.extend([d.embedding for d in resp.data])
        return out


class LocalDevEmbeddingFunction(EmbeddingFunction):
    """Deterministic hashing-based pseudo-embedding for local dev/testing only."""

    def __init__(self, dim: int = LOCAL_DEV_DIM):
        self.dim = dim

    def _embed_one(self, text: str):
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        # unigrams + bigrams gives it a little more discriminative power
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        if not grams:
            return vec
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed_one(t) for t in input]


def get_embedding_function():
    """Returns OpenAI embeddings if OPENAI_API_KEY is set, else the local dev fallback."""
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIEmbeddingFunction()
    print(
        "[embeddings] WARNING: OPENAI_API_KEY not set. Using LocalDevEmbeddingFunction "
        "(hash-based, NOT semantically meaningful). Set OPENAI_API_KEY for real use."
    )
    return LocalDevEmbeddingFunction()
