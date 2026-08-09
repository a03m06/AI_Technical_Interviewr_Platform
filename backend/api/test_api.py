"""
test_api.py
Exercises the full API over HTTP (via TestClient, which runs real
request/response cycles against the ASGI app -- not just calling
Python functions directly) to confirm the FastAPI layer correctly
wraps the LangGraph pause/resume cycle across requests, including the
follow-up probing loop and company-specific mode.
"""

import os
import sys
from pathlib import Path

# isolated sqlite file so test runs don't pollute the real sessions DB
os.environ["CHECKPOINTER_DB_PATH"] = str(Path(__file__).parent.parent / "data" / "test_sessions.sqlite")

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_RESUME = """
Priya — final-year CS student. 2 years of internship experience.
Worked with Python, Django, PostgreSQL, and some AWS. Built a
recommendation engine for a course project. Targeting backend SDE roles.
"""

TEST_ANSWERS = [
    "Use a hashmap.",  # deliberately thin, to exercise the follow-up probe
    "A constructor initializes an object's state when it's created; a destructor cleans up resources when an object is destroyed. Python doesn't have deterministic destructors the way C++ does.",
    "I'd start by clarifying read/write ratio, then design the rate limiter using a token bucket for burst tolerance, backed by Redis so it works across multiple API instances.",
]
FOLLOW_UP_ANSWER = "It's O(n) time and O(n) space, single pass with hashmap lookups."


def run_main_flow():
    print("=== POST /session/start ===")
    resp = client.post("/session/start", json={"resume_text": SAMPLE_RESUME, "max_questions": 3})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    session_id = data["session_id"]
    print(f"session_id={session_id}, status={data['status']}")
    print(f"Q1: [{data['question']['topic']}/{data['question']['difficulty']}] {data['question']['question_text'][:80]}")

    print("\n=== GET /session/{id} (mid-session check) ===")
    resp = client.get(f"/session/{session_id}")
    assert resp.status_code == 200, resp.text
    print(f"status={resp.json()['status']}, question_number={resp.json()['question_number']}")

    round_num = 1
    saw_follow_up = False
    while data["status"] != "complete":
        is_follow_up = data["question"]["is_follow_up"]
        answer = FOLLOW_UP_ANSWER if is_follow_up else TEST_ANSWERS[(round_num - 1) % len(TEST_ANSWERS)]
        label = "follow-up" if is_follow_up else f"round {round_num}"
        print(f"\n=== POST /session/{session_id}/answer ({label}) ===")
        resp = client.post(f"/session/{session_id}/answer", json={"answer": answer})
        assert resp.status_code == 200, resp.text
        data = resp.json()

        if data["last_result"] is not None:
            print(f"finalized score: {data['last_result']['weighted_score']}/10")
        elif data["question"]["is_follow_up"]:
            saw_follow_up = True
            print(f"-> follow-up asked: {data['question']['question_text'][:80]}")

        if data["status"] != "complete" and not data["question"]["is_follow_up"]:
            print(f"Next Q: [{data['question']['topic']}/{data['question']['difficulty']}] {data['question']['question_text'][:80]}")
            round_num += 1

    print("\n=== SESSION COMPLETE ===")
    print("Final report:", data["final_report"])
    print(f"\nFollow-up probing exercised during this session: {saw_follow_up}")
    assert saw_follow_up, "expected the deliberately thin first answer to trigger a follow-up"

    print("\n=== Error handling checks ===")
    resp = client.get("/session/nonexistent-id")
    print(f"GET unknown session_id -> {resp.status_code} (expect 404)")
    assert resp.status_code == 404

    resp = client.post(f"/session/{session_id}/answer", json={"answer": "too late"})
    print(f"POST answer to completed session -> {resp.status_code} (expect 400)")
    assert resp.status_code == 400


def run_company_specific_check():
    print("\n\n=== Company-specific mode check ===")
    resp = client.post(
        "/session/start",
        json={"resume_text": SAMPLE_RESUME, "max_questions": 1, "target_company": "Amazon"},
    )
    assert resp.status_code == 200, resp.text
    q = resp.json()["question"]
    print(f"Q for target_company=Amazon: [{q['topic']}] {q['question_text'][:80]} (source={q['source']})")


if __name__ == "__main__":
    run_main_flow()
    run_company_specific_check()
    print("\nAll checks passed.")
