"""
main.py
FastAPI backend for the AI Technical Interviewer.

Endpoints:
  POST /session/start          -> creates a session, returns the first question
  POST /session/{id}/answer    -> submits an answer, returns the next question
                                   OR the final report if the session is complete
  GET  /session/{id}           -> current session status (for polling/debugging)

Session state lives in the LangGraph checkpointer (MemorySaver, in-process).
session_id doubles as the LangGraph thread_id. This is dev/single-process
only -- swapping MemorySaver for a persistent checkpointer (Postgres/Redis)
is a drop-in change in build_graph.py when this needs to survive restarts
or run across multiple worker processes.
"""
from dotenv import load_dotenv
load_dotenv()
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "graph"))
sys.path.insert(0, str(Path(__file__).parent))  # for `import schemas` when launched as `api.main:app`

from fastapi import FastAPI, HTTPException                     # noqa: E402
from fastapi.middleware.cors import CORSMiddleware              # noqa: E402

from build_graph import build_interview_graph                   # noqa: E402
from schemas import (                                            # noqa: E402
    StartSessionRequest, AnswerRequest, SessionResponse, QuestionOut, RoundResult,
)

app = FastAPI(title="AI Technical Interviewer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = build_interview_graph()
_known_sessions: set[str] = set()  # tracks which thread_ids we've actually created


def _thread(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _question_out(pending: dict, follow_up_text: str | None = None) -> QuestionOut:
    return QuestionOut(
        question_id=pending["question_id"],
        question_text=follow_up_text if follow_up_text is not None else pending["question_text"],
        topic=pending["topic"],
        question_type=pending["question_type"],
        difficulty=pending["difficulty"],
        source=pending.get("source", "generated"),
        is_follow_up=follow_up_text is not None,
    )


def _state_to_response(session_id: str, state: dict, last_result: RoundResult | None = None) -> SessionResponse:
    complete = state.get("session_complete", False)
    follow_up_text = state.get("pending_follow_up") if state.get("is_follow_up") else None
    return SessionResponse(
        session_id=session_id,
        status="complete" if complete else "in_progress",
        question_number=state.get("question_count", 0),
        max_questions=state.get("max_questions", 0),
        question=None if complete else _question_out(state["pending_question"], follow_up_text),
        last_result=last_result,
        final_report=state.get("final_report") if complete else None,
    )


@app.post("/session/start", response_model=SessionResponse)
def start_session(req: StartSessionRequest):
    # graph.invoke() with a fresh thread_id runs resume_parser -> planner ->
    # question_generator, then pauses (interrupt_before=["evaluator"])
    import uuid
    session_id = str(uuid.uuid4())[:12]

    state = _graph.invoke(
        {
            "resume_text": req.resume_text,
            "job_description": req.job_description,
            "max_questions": req.max_questions,
            "target_company": req.target_company,
        },
        config=_thread(session_id),
    )
    _known_sessions.add(session_id)

    return _state_to_response(session_id, state)


@app.post("/session/{session_id}/answer", response_model=SessionResponse)
def submit_answer(session_id: str, req: AnswerRequest):
    if session_id not in _known_sessions:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    thread = _thread(session_id)
    current = _graph.get_state(thread)
    if not current.values or current.values.get("session_complete"):
        raise HTTPException(status_code=400, detail="Session is already complete")

    prior_question = current.values["pending_question"]
    was_follow_up = current.values.get("is_follow_up", False)
    prior_count = current.values.get("question_count", 0)

    _graph.update_state(thread, {"pending_answer": req.answer})
    state = _graph.invoke(None, config=thread)

    # A round only "finalizes" (appends to qa_history, increments question_count)
    # once evaluator scores it -- which may take an extra follow-up round-trip.
    # If evaluator just deferred to a NEW follow-up, there's no result to report yet.
    round_finalized = state.get("question_count", 0) > prior_count or state.get("session_complete")

    last_result = None
    if round_finalized:
        last_round = state["qa_history"][-1]
        last_result = RoundResult(
            question=_question_out(prior_question),
            candidate_answer=last_round["candidate_answer"],
            scores=last_round["scores"],
            weighted_score=last_round["weighted_score"],
            feedback=last_round["feedback"],
        )

    return _state_to_response(session_id, state, last_result=last_result)


@app.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    if session_id not in _known_sessions:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    current = _graph.get_state(_thread(session_id))
    if not current.values:
        raise HTTPException(status_code=404, detail="Session state not found")

    return _state_to_response(session_id, current.values)


@app.get("/health")
def health():
    return {"status": "ok"}