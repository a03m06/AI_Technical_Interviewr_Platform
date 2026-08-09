r"""
build_graph.py
Wires the node functions into a LangGraph StateGraph.

Flow:
  START -> resume_parser -> planner -> question_generator
    -- [graph pauses here (interrupt_before evaluator) for the candidate's answer] --
    -> evaluator -> route_next --continue--> planner
                              \--report----> report_generator -> END

The pause is real LangGraph human-in-the-loop, not a CLI hack: the graph is
compiled with a checkpointer and interrupt_before=["evaluator"], so the
FastAPI layer calls graph.invoke() to get the next question, returns it to
the frontend, then later calls graph.update_state() with the candidate's
answer and graph.invoke(None, ...) again to resume -- across separate HTTP
requests, using session_id as the thread_id.

Checkpointer:
  CHECKPOINTER=sqlite (default) -- persists sessions to a local .sqlite
    file (CHECKPOINTER_DB_PATH, default data/sessions.sqlite). Survives
    process restarts. Fine for a single-process deployment; for multiple
    worker processes or real production scale, swap to
    langgraph.checkpoint.postgres.PostgresSaver -- same call sites, only
    get_checkpointer() below changes.
  CHECKPOINTER=memory -- in-process only, lost on restart. Useful for
    quick tests/CI where you don't want a stray .sqlite file left behind.
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import InterviewState
from nodes import (
    resume_parser_node,
    planner_node,
    question_generator_node,
    follow_up_prober_node,
    evaluator_node,
    report_generator_node,
    route_next,
    route_after_evaluation,
)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "sessions.sqlite"


def get_checkpointer():
    """
    Returns (checkpointer, cleanup_fn). cleanup_fn is a no-op for MemorySaver;
    for SqliteSaver it closes the underlying connection -- call it on app
    shutdown if you want a clean close (not required for correctness with
    SQLite, but tidy).
    """
    kind = os.environ.get("CHECKPOINTER", "sqlite").lower()

    if kind == "memory":
        return MemorySaver(), (lambda: None)

    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = os.environ.get("CHECKPOINTER_DB_PATH", str(DEFAULT_DB_PATH))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()  # creates the checkpoint tables if they don't exist yet
    return saver, conn.close


def build_interview_graph():
    graph = StateGraph(InterviewState)

    graph.add_node("resume_parser", resume_parser_node)
    graph.add_node("planner", planner_node)
    graph.add_node("question_generator", question_generator_node)
    graph.add_node("follow_up_prober", follow_up_prober_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("report_generator", report_generator_node)

    graph.add_edge(START, "resume_parser")
    graph.add_edge("resume_parser", "planner")
    graph.add_edge("planner", "question_generator")
    graph.add_edge("question_generator", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {"follow_up": "follow_up_prober", "continue": "planner", "report": "report_generator"},
    )
    graph.add_edge("follow_up_prober", "evaluator")
    graph.add_edge("report_generator", END)

    checkpointer, _cleanup = get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer, interrupt_before=["evaluator"])
    compiled._cleanup = _cleanup  # stashed for callers that want to close the DB connection on shutdown
    return compiled


if __name__ == "__main__":
    # Smoke test: build the graph and print its node list, no execution.
    g = build_interview_graph()
    print("Graph built successfully. Nodes:", list(g.get_graph().nodes.keys()))
    print("Checkpointer:", os.environ.get("CHECKPOINTER", "sqlite"))
