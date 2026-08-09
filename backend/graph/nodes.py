"""
nodes.py
The actual node functions in the interview graph. Each takes the current
InterviewState and returns a partial dict to merge into it.

Graph flow (see build_graph.py for the wiring):
  resume_parser -> planner -> question_generator -> [PAUSE for answer]
    -> evaluator -> route_next -> (loop to planner, or -> report_generator -> END)
"""
import random
import sys
from pathlib import Path

# rag/ modules use bare imports (designed to also run standalone via
# `python vector_store.py`), so we add it to sys.path rather than
# refactor them into a relative-import package.
sys.path.insert(0, str(Path(__file__).parent.parent / "rag"))

from vector_store import query_questions          # noqa: E402
from eval_store import get_evaluation_context      # noqa: E402
import llm                                          # noqa: E402

MAX_QUESTIONS_DEFAULT = 6
DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]

# Rotation of topics a session covers, in priority order. In company-specific
# mode this could be re-weighted toward that company's tag distribution --
# left as a fixed rotation here since that's a planner refinement, not a
# graph-structure concern.
TOPIC_ROTATION = ["DSA", "OOP", "System Design", "LLD", "OS", "DBMS", "Behavioral"]


MAX_FOLLOW_UPS_PER_QUESTION = 1

def _allocate_topic_plan(topic_weights: dict, length: int) -> list[str]:
    """
    Converts topic_weights into a concrete list of `length` topics using the
    largest-remainder method (so rounding errors don't silently drop a topic
    that deserved 1 slot), then shuffles with a no-consecutive-duplicate pass
    so the session doesn't ask e.g. two Python questions back to back just
    because Python got the largest allocation.
    """
    if not topic_weights:
        return list(TOPIC_ROTATION)[:length] or [TOPIC_ROTATION[0]] * length

    raw = {t: w * length for t, w in topic_weights.items()}
    floor_counts = {t: int(v) for t, v in raw.items()}
    remainder = length - sum(floor_counts.values())
    # distribute leftover slots to the topics with the largest fractional remainder
    fractions = sorted(raw.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True)
    for topic, _ in fractions[:remainder]:
        floor_counts[topic] += 1

    plan = []
    for topic, count in floor_counts.items():
        plan.extend([topic] * count)
    plan = plan[:length]
    while len(plan) < length:  # safety pad, shouldn't normally trigger
        plan.append(TOPIC_ROTATION[0])

    random.shuffle(plan)
    # light de-clustering pass: swap forward if two identical topics land adjacent
    for i in range(1, len(plan)):
        if plan[i] == plan[i - 1]:
            for j in range(i + 1, len(plan)):
                if plan[j] != plan[i - 1]:
                    plan[i], plan[j] = plan[j], plan[i]
                    break
    return plan

def resume_parser_node(state: dict) -> dict:
    profile = llm.parse_resume(state["resume_text"], state.get("job_description"))
    if state.get("target_company"):
        profile["target_company"] = state["target_company"]
    else:
        profile.setdefault("target_company", None)

    max_q = state.get("max_questions") or MAX_QUESTIONS_DEFAULT
    topic_plan = _allocate_topic_plan(profile.get("topic_weights", {}), max_q)

    return {
        "candidate_profile": profile,
        "session_id": llm.new_session_id(),
        "max_questions": max_q,
        "topic_plan": topic_plan,
        "topic_competence": {},
        "question_count": 0,
        "follow_up_count": 0,
        "session_complete": False,
    }


def planner_node(state: dict) -> dict:
    competence = state.get("topic_competence", {})
    q_index = state.get("question_count", 0)
    topic_plan = state.get("topic_plan") or TOPIC_ROTATION

    topic = topic_plan[q_index] if q_index < len(topic_plan) else topic_plan[q_index % len(topic_plan)]

    topic_state = competence.get(topic, {"correct_streak": 0, "attempts": 0, "running_score": 5.0})
    if topic_state["correct_streak"] >= 2:
        idx = min(len(DIFFICULTY_ORDER) - 1, DIFFICULTY_ORDER.index("Medium") + 1)
    elif topic_state["attempts"] > 0 and topic_state["running_score"] < 4.0:
        idx = max(0, DIFFICULTY_ORDER.index("Medium") - 1)
    else:
        idx = DIFFICULTY_ORDER.index("Medium")
    difficulty = DIFFICULTY_ORDER[idx]

    question_type = "Behavioral" if topic == "Behavioral" else (
        "Coding" if topic == "DSA" else ("Design" if topic in ("System Design", "LLD") else "Theory")
    )

    return {
        "current_topic": topic,
        "current_difficulty": difficulty,
        "current_question_type": question_type,
    }


def question_generator_node(state: dict) -> dict:
    """Hybrid retrieve+adapt: pulls seed questions from the RAG bank, then
    lets the LLM pick or adapt one to fit the candidate profile/difficulty.

    Company-specific mode: if candidate_profile.target_company is set, first
    tries retrieval scoped to that company's tagged questions. The bank is
    thin for smaller companies (some have only 1-2 tagged questions), so if
    that scoped retrieval comes up empty we fall back to the general pool
    rather than surface a generation error mid-session."""
    topic = state["current_topic"]
    difficulty = state["current_difficulty"]
    qtype = state["current_question_type"]
    profile = state.get("candidate_profile", {})
    asked = state.get("asked_question_ids", [])
    target_company = profile.get("target_company")

    query_text = f"{topic} {qtype} question for a {profile.get('target_role', 'Software Engineer')}"

    seeds = []
    if target_company:
        seeds = query_questions(
            query_text=query_text, n_results=5, company=target_company,
            topic=topic, difficulty=difficulty, question_type=qtype, exclude_ids=asked,
        )
        if not seeds:
            # company pool too thin for this exact topic/difficulty/type combo -- widen to
            # just the company + topic before giving up on company-specific mode entirely
            seeds = query_questions(
                query_text=query_text, n_results=5, company=target_company, topic=topic, exclude_ids=asked,
            )

    if not seeds:
        seeds = query_questions(
            query_text=query_text, n_results=5, topic=topic, difficulty=difficulty,
            question_type=qtype, exclude_ids=asked,
        )
    if not seeds:
        seeds = query_questions(query_text=f"{topic} question", n_results=5, topic=topic, exclude_ids=asked)

    result = llm.adapt_question(seeds, profile, difficulty, topic)

    question_id = result.get("seed_id") or f"generated:{llm.new_session_id()}"
    pending = {
        "question_id": question_id,
        "question_text": result["question_text"],
        "topic": topic,
        "question_type": qtype,
        "difficulty": difficulty,
        "source": result.get("source", "generated"),
    }

    return {
        "pending_question": pending,
        "asked_question_ids": [question_id],
        "pending_answer": None,
        "follow_up_count": 0,
        "is_follow_up": False,
    }


def evaluator_node(state: dict) -> dict:
    """
    Retrieves grounding for the question, then either:
    (a) scores the answer and finalizes the round, or
    (b) if the answer looks thin/incomplete and no follow-up has been asked
        yet for this question, defers scoring and asks one follow-up probe
        instead (capped at MAX_FOLLOW_UPS_PER_QUESTION).
    Called again after the follow-up is answered (is_follow_up=True), where
    it always finalizes using the initial + follow-up answers combined.
    """
    question = state["pending_question"]
    answer = state.get("pending_answer") or ""
    is_follow_up = state.get("is_follow_up", False)
    follow_up_count = state.get("follow_up_count", 0)

    ctx = get_evaluation_context(
        question_text=question["question_text"],
        topic=question["topic"],
        question_type=question["question_type"],
    )

    if not is_follow_up and follow_up_count < MAX_FOLLOW_UPS_PER_QUESTION:
        probe = llm.probe_follow_up(question, answer, ctx["grounding"])
        if probe.get("needs_follow_up") and probe.get("follow_up_question"):
            return {
                "initial_answer": answer,
                "follow_up_count": follow_up_count + 1,
                "pending_follow_up": probe["follow_up_question"],
                "is_follow_up": True,
                "pending_answer": None,
            }

    if is_follow_up:
        initial_answer = state.get("initial_answer") or ""
        combined_answer = (
            f"{initial_answer}\n\n[Follow-up Q]: {state.get('pending_follow_up', '')}\n"
            f"[Follow-up A]: {answer}"
        )
    else:
        combined_answer = answer

    result = llm.evaluate_answer(question, combined_answer, ctx["rubric"], ctx["grounding"])

    qa_round = {
        **question,
        "candidate_answer": combined_answer,
        "scores": result["scores"],
        "weighted_score": result["weighted_score"],
        "feedback": result["feedback"],
        "had_follow_up": is_follow_up,
    }

    # update running competence for this topic
    topic = question["topic"]
    competence = dict(state.get("topic_competence", {}))
    prev = competence.get(topic, {"correct_streak": 0, "attempts": 0, "running_score": 5.0})
    is_strong = result["weighted_score"] >= 7.0
    new_attempts = prev["attempts"] + 1
    # weighted moving average, weighted toward recent performance
    new_running = round((prev["running_score"] * prev["attempts"] + result["weighted_score"]) / new_attempts, 2) \
        if prev["attempts"] < 3 else round(prev["running_score"] * 0.6 + result["weighted_score"] * 0.4, 2)
    competence[topic] = {
        "correct_streak": prev["correct_streak"] + 1 if is_strong else 0,
        "attempts": new_attempts,
        "running_score": new_running,
    }

    return {
        "qa_history": [qa_round],
        "topic_competence": competence,
        "question_count": state.get("question_count", 0) + 1,
        "pending_follow_up": None,
        "is_follow_up": False,
        "initial_answer": None,
    }


def follow_up_prober_node(state: dict) -> dict:
    """
    Pass-through node. Its only purpose is to sit between evaluator's
    "needs a follow-up" branch and the loop back to evaluator, so that
    interrupt_before=["evaluator"] pauses the graph here -- giving the API
    layer a chance to surface state["pending_follow_up"] to the candidate
    and collect their follow-up answer before evaluator runs again.
    """
    return {}


def route_next(state: dict) -> str:
    """Conditional edge: keep asking, or wrap up the session."""
    if state.get("question_count", 0) >= state.get("max_questions", MAX_QUESTIONS_DEFAULT):
        return "report"
    return "continue"


def route_after_evaluation(state: dict) -> str:
    """
    Conditional edge out of evaluator. Distinguishes "evaluator just deferred
    to a follow-up probe" (pending_follow_up is set) from "evaluator just
    finalized a round" (pending_follow_up is None), then in the latter case
    delegates to route_next for the continue-vs-wrap-up decision.
    """
    if state.get("pending_follow_up"):
        return "follow_up"
    return route_next(state)


def report_generator_node(state: dict) -> dict:
    report = llm.generate_report(state.get("qa_history", []), state.get("topic_competence", {}))
    return {
        "final_report": report,
        "session_complete": True,
    }
