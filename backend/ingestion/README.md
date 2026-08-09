# Ingestion pipeline — Step 1 (done)

## What this does
1. `clean_data.py` — normalizes the raw 618-question bank (fixes casing,
   dedupes overlapping question_type/topic labels, adds a `search_text`
   field per record) → writes `data/questions_clean.json`.
2. `rag/vector_store.py` — embeds each question and stores it in a
   persistent ChromaDB collection at `data/chroma_store/`, with
   company/topic/difficulty/question_type/year kept as filterable metadata.
3. `rag/embeddings.py` — the embedding backend. Uses real OpenAI embeddings
   (`text-embedding-3-small`) when `OPENAI_API_KEY` is set. Falls back to a
   deterministic local hash-based embedding when it isn't, purely so the
   pipeline can be built/tested without hitting the network — **do not use
   the fallback for the real app**, it's not semantically meaningful.

## How to run it yourself
```bash
cd backend
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...

python ingestion/clean_data.py        # -> data/questions_clean.json
python rag/vector_store.py            # -> builds data/chroma_store/
```

## How to query it (used by the Question Generator Agent later)
```python
from rag.vector_store import query_questions

hits = query_questions(
    query_text="binary search on rotated array",
    n_results=5,
    company="Amazon",       # optional
    topic="DSA",            # optional
    difficulty="Medium",    # optional
)
```

## Verified locally (with the dev fallback embedding)
- All 618 questions indexed successfully into the `interview_questions` collection.
- Metadata filtering (company/topic/difficulty) works correctly combined with semantic query.
- Re-running `vector_store.py` is idempotent (`upsert`, not `insert`) — safe to re-run after data changes.

## Known data quirks worth knowing about
- 477 of 618 questions have `company: "General"` (company-agnostic) — only
  141 are tagged to a specific company. Good for general prep, thinner for
  company-specific mode on smaller companies (e.g., only 2 Adobe questions).
- Topic labels have a long tail — beyond the ~15 major topics (DSA, OOP,
  System Design, ML, OS, LLD, Behavioral, SQL, CN, DBMS...), there are ~50
  niche AI/ML topics with 1-4 questions each (Diffusion Models, GANs, PEFT,
  etc.). Fine for retrieval, but not enough volume to build a full adaptive
  session around a niche topic alone.
- Only 68 questions have a `year` (2025); the rest are undated. Don't rely
  on year filtering unless you're okay with a small pool.

---

# Step 2 (done): evaluation corpus

## What this does
1. `generate_eval_corpus.py` — 38 original canonical explanation entries
   covering the highest-volume topics/tags in the question bank (DSA
   patterns, OOP, System Design, LLD, OS, DBMS/SQL, Networking, language
   fundamentals, ML/LLM/RAG concepts, Behavioral STAR method, Aptitude).
   Each entry has an explanation, key points a strong answer should hit,
   and common pitfalls → `data/canonical_explanations.json`.
2. `rubrics.py` — scoring rubrics for the 4 question types (Coding, Theory,
   Design, Behavioral), each a weighted list of criteria summing to 1.0 →
   `data/rubrics.json`.
3. `rag/eval_store.py` — second ChromaDB collection (`canonical_explanations`)
   plus `get_evaluation_context(question_text, topic, question_type)`, the
   single function the Evaluation Agent node calls. It returns the correct
   rubric (direct dict lookup, not RAG — only 4 types, no ambiguity) plus
   the top-2 retrieved canonical explanations for grounding.

## Topic alignment (important)
The question bank uses ~75 granular topic labels ("Array", "Tree",
"Dynamic Programming", "PEFT", "Hugging Face"...); the canonical corpus is
authored at a broader grain ("DSA", "System Design", "LLM"). `eval_store.py`
has a `TOPIC_GROUP_MAP` that resolves the former to the latter before
filtering — without it, topic-filtered retrieval silently misses on most
questions and falls back to an unfiltered search every time. Verified this
resolves correctly across DSA/LLD/SQL/OS/LLM/OOP test cases.

## Content sourcing note
Per copyright constraints, the canonical explanations are original
synthesis (not scraped from GeeksforGeeks/LeetCode/etc.) — same effect for
grounding purposes (the Evaluation Agent just needs an accurate reference
to score against), without the legal risk of ingesting third-party content
at scale. Real official documentation (Python docs, MDN, etc.) can be
layered in later for topics where that's freely referenceable.

## Coverage gaps (honest accounting)
38 entries is a solid starter set for the highest-volume topics, but it's
not 1:1 with the question bank's full topic list — niche areas (Diffusion
Models, GANs, VAE, individual AI-agent subtopics) will fall back to an
unfiltered semantic search rather than a topic-matched one. Fine for now;
expand `CORPUS` in `generate_eval_corpus.py` as those topics come up more.

## How to run it yourself
```bash
cd backend
export OPENAI_API_KEY=sk-...

python ingestion/generate_eval_corpus.py   # -> data/canonical_explanations.json
python ingestion/rubrics.py                # -> data/rubrics.json
python rag/eval_store.py                   # -> builds the canonical_explanations collection
```

## How to use it (Evaluation Agent)
```python
from rag.eval_store import get_evaluation_context

ctx = get_evaluation_context(
    question_text="Given a string of ( and ), find the longest valid substring.",
    topic="Dynamic Programming",   # the question's raw topic field -- mapped internally
    question_type="Coding",
)
# ctx["rubric"]      -> weighted scoring criteria for Coding questions
# ctx["grounding"]   -> top-2 canonical explanations to ground the score against
```

---

# Step 3 (done): LangGraph skeleton

## What this does
`graph/` wires the RAG stores and LLM wrapper into an actual LangGraph
`StateGraph`:

- `state.py` — the `InterviewState` schema flowing through every node
  (candidate profile, per-topic competence tracking, accumulated Q&A
  history, control-flow flags).
- `llm.py` — the LLM wrapper. Real OpenAI calls when `OPENAI_API_KEY` is
  set; a mock backend otherwise so the graph can be built/tested without
  network access. Four functions: `parse_resume`, `adapt_question`,
  `evaluate_answer`, `generate_report` — nodes only ever call these, never
  the OpenAI client directly.
- `nodes.py` — the five node functions:
  - `resume_parser_node` — extracts candidate profile
  - `planner_node` — picks next topic/difficulty, adapting on running
    per-topic competence (raises difficulty on a 2+ correct streak, lowers
    it after a weak score)
  - `question_generator_node` — **the hybrid mode**: retrieves seed
    questions from `vector_store.query_questions()`, then
    `llm.adapt_question()` either picks one verbatim or adapts it to the
    candidate's stack/difficulty
  - `evaluator_node` — retrieves grounding via
    `eval_store.get_evaluation_context()`, scores the answer against the
    rubric, updates running topic competence
  - `report_generator_node` — aggregates the full session
- `build_graph.py` — the actual `StateGraph` wiring, compiled with a
  `MemorySaver` checkpointer and `interrupt_before=["evaluator"]` — this is
  real LangGraph human-in-the-loop, not a CLI hack. The graph pauses after
  generating a question; the caller (CLI now, FastAPI in Step 4) writes the
  candidate's answer into state and resumes.
- `cli.py` — interactive (or auto-answer, for unattended testing) runner
  that exercises the full pause/resume cycle end-to-end.

## Verified locally (mock LLM + dev embeddings)
Ran a full 4-question session end-to-end: resume parsed -> profile built ->
4 rounds of plan -> generate (mix of verbatim and adapted questions pulled
from the real 618-question bank) -> pause -> answer -> resume -> evaluate
(grounded against the correct topic bucket each time) -> final report
generated. Pause/resume across separate `graph.invoke()` calls on the same
`thread_id` confirmed working.

## How to run it yourself
```bash
cd backend
export OPENAI_API_KEY=sk-...        # omit to run against the mock LLM instead
python graph/build_graph.py         # smoke test: builds the graph, prints node list
python graph/cli.py                 # full session with canned test answers
```
To try it interactively with your own answers, edit `cli.py`'s `__main__`
block to call `run_session(SAMPLE_RESUME, max_questions=4)` without
`auto_answers` — it'll prompt you for real input at each question.

## What's still mock/simplified (be aware before demoing)
- The mock LLM's scoring is a crude word-count heuristic, not real
  evaluation — only meaningful once `OPENAI_API_KEY` is set.
- `planner_node`'s topic rotation and difficulty adjustment logic is a
  reasonable first pass, not tuned against real interview data.
- Company-specific mode (weighting topics by a target company's actual tag
  distribution) isn't wired in yet — `question_generator_node` doesn't pass
  `company` to `query_questions()` currently.

## Next step
Step 4: FastAPI backend exposing session endpoints (start/answer/report),
wrapping graph.invoke()/update_state() across HTTP requests using
session_id as the LangGraph thread_id.

---

# Step 4 (done): FastAPI backend

## What this does
`api/` exposes the graph as a real HTTP service:

- `main.py` — three endpoints:
  - `POST /session/start` `{resume_text, max_questions?}` -> creates a
    session (session_id doubles as the LangGraph thread_id), runs the
    graph to the first question, returns it
  - `POST /session/{id}/answer` `{answer}` -> writes the answer into graph
    state and resumes; returns either the next question or, once
    `max_questions` is reached, the final report
  - `GET /session/{id}` -> current status, for polling/debugging without
    submitting an answer
  - `GET /health` -> basic liveness check
- `schemas.py` — Pydantic request/response models (also gives you free
  OpenAPI docs at `/docs` once the server is running)
- Session state lives in the graph's `MemorySaver` checkpointer
  (in-process, dev-only — see note below on persistence)

## Verified locally (real HTTP, not just function calls)
`test_api.py` runs the full lifecycle through `TestClient` (a real
ASGI request/response cycle, not calling Python functions directly):
session start -> mid-session `GET` poll -> 3 rounds of `POST .../answer`
each returning the next question -> completion with final report ->
both error paths (`404` on an unknown session_id, `400` on answering an
already-completed session). All passed.

## How to run it yourself
```bash
cd backend
export OPENAI_API_KEY=sk-...        # omit to run against the mock LLM
uvicorn api.main:app --reload --port 8000
```
Then either open `http://localhost:8000/docs` for interactive Swagger UI,
or run `python api/test_api.py` against a running server (or standalone,
since `TestClient` spins the app up in-process).

## Known limitation: session persistence
`MemorySaver` keeps session state in the Python process's memory — it's
gone on server restart, and won't work correctly if you run multiple
uvicorn worker processes (each would have its own separate memory). Fine
for local dev and demos. For real deployment, swap `MemorySaver` for
`langgraph.checkpoint.postgres.PostgresSaver` (or Redis) in
`graph/build_graph.py` — the rest of the code doesn't need to change,
since it only interacts with the checkpointer through the compiled
graph's `invoke`/`update_state`/`get_state` calls.

## Next step
Step 5 options from here: (a) frontend (React chat-style interview UI +
report dashboard), or (b) hardening the backend first — persistent
checkpointer, auth-lite per session, rate limiting on LLM calls. Worth
deciding based on whether you want a demoable UI sooner or a more
production-shaped backend first.
