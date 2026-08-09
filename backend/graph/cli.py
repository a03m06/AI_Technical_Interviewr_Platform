"""
cli.py
Interactive command-line runner for the interview graph. Demonstrates the
real pause/resume cycle: invoke() runs until interrupt_before=["evaluator"]
kicks in, we print the question, collect the candidate's answer, write it
into state, then invoke(None, ...) resumes from evaluator using the same
thread_id.

Run with no OPENAI_API_KEY set to exercise the mock LLM end-to-end (as
tested below); export OPENAI_API_KEY for real questions/scoring.
"""

import sys
from build_graph import build_interview_graph

SAMPLE_RESUME = """
Mohit — Software Engineering student, AI Engineering minor.
3 years of project experience. Built a commercial AI Stock Analyser
platform (Python, FastAPI, React, LangGraph, RAG). Comfortable with
Python, SQL, and system design fundamentals. Looking for SDE roles.
"""


def run_session(resume_text: str, max_questions: int = 4, auto_answers: list[str] | None = None):
    graph = build_interview_graph()
    thread = {"configurable": {"thread_id": "cli-session-1"}}

    state = graph.invoke(
        {"resume_text": resume_text, "max_questions": max_questions},
        config=thread,
    )

    round_num = 0
    while not state.get("session_complete"):
        q = state["pending_question"]
        is_follow_up = state.get("is_follow_up", False)
        prompt_text = state.get("pending_follow_up") if is_follow_up else q["question_text"]

        if not is_follow_up:
            round_num += 1
            print(f"\n--- Question {round_num} [{q['topic']} / {q['difficulty']} / {q['question_type']}] ---")
            print(f"(source: {q.get('source', 'generated')}, seed_id: {q.get('question_id')})")
        else:
            print("\n  --- Follow-up ---")
        print(prompt_text)

        if auto_answers:
            if is_follow_up:
                answer = "It's O(n) time and O(n) space since we do a single pass with a hashmap lookup."
            else:
                answer = auto_answers[(round_num - 1) % len(auto_answers)]
            print(f"\n[auto-answer]: {answer[:100]}{'...' if len(answer) > 100 else ''}")
        else:
            answer = input("\nYour answer: ")

        graph.update_state(thread, {"pending_answer": answer})
        state = graph.invoke(None, config=thread)

        if not state.get("is_follow_up") and not state.get("session_complete") and state.get("qa_history"):
            last_round = state["qa_history"][-1]
            print(f"Score: {last_round['weighted_score']}/10 -- {last_round['feedback']}")
        elif state.get("session_complete"):
            last_round = state["qa_history"][-1]
            print(f"Score: {last_round['weighted_score']}/10 -- {last_round['feedback']}")

    print("\n=== FINAL REPORT ===")
    report = state["final_report"]
    for k, v in report.items():
        print(f"{k}: {v}")

    return state


if __name__ == "__main__":
    # Non-interactive smoke test with canned answers, so this can run
    # unattended in CI/sandbox as well as interactively.
    test_answers = [
        "Use a hashmap.",
        "Encapsulation hides internal state behind methods, inheritance lets a subclass reuse a parent's behavior, polymorphism lets you call the same method name on different types and get type-specific behavior at runtime.",
        "I'd shard the database by user_id hash to distribute write load, and add a read-replica layer behind a cache for hot reads, with the cache using a TTL-based invalidation to bound staleness.",
        "In my last group project I noticed our deploy pipeline had no rollback path. I proposed and implemented a blue-green deploy script so we could revert in under a minute, which we actually used twice during launch week.",
        "Explained the approach and its tradeoffs in detail, covering time complexity and edge cases as well.",
    ]
    run_session(SAMPLE_RESUME, max_questions=4, auto_answers=test_answers)
