# AI Technical Interviewer — Backend

A multi-agent technical interview platform built on LangGraph, RAG, and an
LLM (OpenAI), using a real 618-question interview bank as its grounding
data. This README is the top-level guide; `ingestion/README.md` has the
detailed step-by-step build log if you want the full history/rationale.

## Architecture

```
                    START
                      |
                resume_parser  --  parses candidate profile from resume text
                      |
                   planner  --  picks next topic/difficulty from running
                      |         per-topic competence (adaptive)
                      v
            question_generator  --  hybrid RAG: retrieves seed questions
                      |             from the real question bank, LLM picks
                      |             verbatim or adapts to candidate/difficulty
                      |
           [PAUSE -- graph waits for the candidate's answer]
                      |
                  evaluator  --  retrieves grounding from the canonical
                    |   |        explanations corpus, scores against a
                    |   |        weighted rubric (by question type)
       needs         |   no follow-up needed / follow-up already used
    follow-up?        \        /
          |            \      /
          v              v    v
  follow_up_prober    route_after_evaluation
          |                |         \
   [PAUSE again]      continue      report
          |                |            |
          +----------> evaluator    report_generator --> END
                       (re-enters,        (aggregates full
                        combines            session into
                        both answers)       final report)
```

## What's real vs. mock

Everything runs against a **mock LLM** by default (no `OPENAI_API_KEY`
needed) so the graph/API can be tested without burning API credits. Set
`OPENAI_API_KEY` and every LLM-backed call (`llm.py`'s four functions:
resume parsing, question adaptation, answer evaluation, follow-up probing,
report generation) automatically switches to real GPT calls — no code
changes needed anywhere else. The mock scoring is a crude word-count
heuristic; treat any score you see without a real key as a plumbing check,
not a real evaluation.

Embeddings work the same way: `rag/embeddings.py` uses real OpenAI
embeddings when the key is set, and a deterministic local hash-based
fallback otherwise (also clearly not semantically meaningful — for
testing retrieval *logic*, not retrieval *quality*).

## Project layout

```
backend/
├── data/                          question bank + generated corpora (JSON)
│   ├── interview_question_bank_final.json   (your original upload, untouched)
│   ├── questions_clean.json                 (normalized, from clean_data.py)
│   ├── canonical_explanations.json          (38 grounding entries)
│   ├── rubrics.json                         (scoring criteria by question type)
│   └── chroma_store/, sessions.sqlite       (generated at runtime, gitignored)
├── ingestion/
│   ├── clean_data.py               normalizes the raw question bank
│   ├── generate_eval_corpus.py     writes canonical_explanations.json
│   ├── rubrics.py                  writes rubrics.json
│   └── README.md                   detailed step-by-step build log
├── rag/
│   ├── embeddings.py                embedding backend (OpenAI or dev fallback)
│   ├── vector_store.py              question bank collection + query_questions()
│   └── eval_store.py                canonical explanations collection +
│                                     get_evaluation_context() + topic-group mapping
├── graph/
│   ├── state.py                     InterviewState schema
│   ├── llm.py                       LLM wrapper (real + mock backends)
│   ├── nodes.py                     the 6 graph nodes
│   ├── build_graph.py               StateGraph wiring + checkpointer selection
│   └── cli.py                       interactive/auto-answer test runner
├── api/
│   ├── main.py                      FastAPI app (3 endpoints)
│   ├── schemas.py                   Pydantic request/response models
│   └── test_api.py                  full-lifecycle HTTP test
├── requirements.txt
├── .env.example
└── Dockerfile
```

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # fill in OPENAI_API_KEY, or leave unset for mock mode
export $(cat .env | xargs)  # or just export OPENAI_API_KEY=sk-... directly

# Build the RAG collections (run once, or whenever data/*.json changes)
python ingestion/clean_data.py
python ingestion/generate_eval_corpus.py
python ingestion/rubrics.py
python rag/vector_store.py
python rag/eval_store.py
```

## Running it

**CLI (fastest way to see it work):**
```bash
python graph/cli.py
```

**API server:**
```bash
uvicorn api.main:app --reload --port 8000
# then open http://localhost:8000/docs for interactive Swagger UI
```

**Docker:**
```bash
docker build -t ai-interviewer-backend .
docker run -p 8000:8000 --env-file .env ai-interviewer-backend
```

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/session/start` | POST | `{resume_text, max_questions?, target_company?}` -> first question |
| `/session/{id}/answer` | POST | `{answer}` -> next question, a follow-up probe, or the final report |
| `/session/{id}` | GET | current status, for polling without submitting an answer |
| `/health` | GET | liveness check |

Watch `question.is_follow_up` in the response: when `true`, the frontend
should present it as a quick follow-up (not a fresh numbered question) and
POST the answer to the same `/answer` endpoint — the graph handles
combining it with the original answer for scoring internally.

## Features implemented

- **Hybrid RAG question generation** — retrieves real questions from your
  618-question bank, LLM decides verbatim vs. adapted per candidate/difficulty
- **Grounded evaluation** — scores against a 38-entry canonical explanation
  corpus + weighted rubrics per question type, not just LLM impression
- **Adaptive difficulty** — planner raises/lowers difficulty per topic based
  on a running competence score, not a fixed script
- **Follow-up probing** — evaluator can defer scoring once per question to
  ask a targeted follow-up when an answer looks thin, then scores both
  together (capped at 1 follow-up/question to keep sessions moving)
- **Company-specific mode** — pass `target_company` to scope retrieval to
  that company's tagged questions, with automatic graceful fallback to the
  general pool for topics/companies the bank is thin on (verified with
  Adobe, which has only 2 tagged questions)
- **Persistent sessions** — SQLite-backed checkpointer by default; survives
  server restarts (verified across separate Python processes)

## Known limitations (be upfront about these)

- **SQLite checkpointer is single-process.** Fine for one uvicorn worker;
  won't coordinate correctly across multiple worker processes. For that,
  swap to `langgraph.checkpoint.postgres.PostgresSaver` in
  `build_graph.py`'s `get_checkpointer()` — the rest of the code doesn't
  change, since everything else only touches the checkpointer through the
  compiled graph's `invoke`/`update_state`/`get_state`.
- **Canonical explanation corpus covers ~38 core concepts**, not all ~75
  granular topics in the question bank. Niche AI/ML subtopics (Diffusion
  Models, GANs, individual agent-safety topics) fall back to an unfiltered
  semantic search rather than a topic-matched one.
- **No auth.** Anyone with a `session_id` can answer that session. Fine for
  a portfolio/demo; add auth before any real deployment.
- **No rate limiting** on LLM calls — a malicious or buggy client could run
  up API costs. Worth adding before a public deployment.
- **CORS is wide open** (`allow_origins=["*"]`) — tighten before production.

## Next step (not built yet)

Frontend — a React chat-style interview UI + report dashboard, wired to
these three endpoints. Deliberately deferred; this backend is fully
testable and demoable via `graph/cli.py` and `/docs` without one.
