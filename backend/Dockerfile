FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The RAG collections must be built once before the API can serve real
# retrieval -- run this at image build time so the container starts ready.
# Uses the mock embedding fallback if OPENAI_API_KEY isn't available at
# BUILD time; pass it as a build secret/arg for real embeddings baked into
# the image, or just run these two commands again after container start
# with the key set in the environment.
RUN python ingestion/clean_data.py && \
    python ingestion/generate_eval_corpus.py && \
    python ingestion/rubrics.py

EXPOSE 8000

# Vector store + eval collections are built lazily on first import via
# rag/vector_store.py's `if __name__ == "__main__"` guard -- here we build
# them explicitly so the first request isn't slow. Requires network access
# to OpenAI at container start (real embeddings) unless CHECKPOINTER/embedding
# fallback envs are set for local-only testing.
CMD ["sh", "-c", "python rag/vector_store.py && python rag/eval_store.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
