"""
state.py

The shared state object that flows through every node in the interview graph.

LangGraph merges partial dict returns from each node into this state
using the reducers defined below (Annotated + operator.add for lists
that should accumulate, plain overwrite for everything else).
"""

import operator
from typing import TypedDict, Annotated, Literal


# ============================================================
# Candidate Profile
# ============================================================

class CandidateProfile(TypedDict, total=False):
    # Parsed from resume
    years_experience: int

    # Technologies detected from resume
    primary_stack: list[str]

    # Topics where candidate appears strongest
    strongest_topics: list[str]

    # Software Engineer / AI Engineer / SDE Intern etc.
    target_role: str

    # Optional interview company
    target_company: str | None

    # Relative importance of interview topics.
    # Generated from Resume + Job Description.
    #
    # Example:
    # {
    #     "Python": 0.30,
    #     "React": 0.20,
    #     "SQL": 0.15,
    #     "System Design": 0.20,
    #     "Behavioral": 0.15
    # }
    #
    # Sum should be approximately 1.0
    topic_weights: dict[str, float]


# ============================================================
# One completed QA round
# ============================================================

class QARound(TypedDict):
    question_id: str
    question_text: str

    topic: str
    question_type: str            # Coding | Theory | Design | Behavioral
    difficulty: str               # Easy | Medium | Hard

    candidate_answer: str

    scores: dict                  # {criterion: score}
    weighted_score: float         # Final 0-10 score

    feedback: str


# ============================================================
# Running topic competence
# ============================================================

class TopicCompetence(TypedDict):
    correct_streak: int
    attempts: int
    running_score: float


# ============================================================
# Interview State
# ============================================================

class InterviewState(TypedDict, total=False):

    # --------------------------------------------------------
    # Session Setup
    # --------------------------------------------------------

    resume_text: str

    # Optional Job Description pasted by the user
    job_description: str | None

    # Explicit company selected by user
    target_company: str | None

    candidate_profile: CandidateProfile

    session_id: str

    max_questions: int


    # --------------------------------------------------------
    # Interview Planning
    # --------------------------------------------------------

    current_topic: str

    current_difficulty: Literal[
        "Easy",
        "Medium",
        "Hard"
    ]

    current_question_type: str

    # Pre-computed interview roadmap.
    #
    # Example:
    # [
    #     "Python",
    #     "React",
    #     "SQL",
    #     "System Design",
    #     "Behavioral"
    # ]
    topic_plan: list[str]

    topic_competence: dict[str, TopicCompetence]

    asked_question_ids: Annotated[
        list[str],
        operator.add
    ]


    # --------------------------------------------------------
    # Current Question
    # --------------------------------------------------------

    # Original question
    pending_question: dict

    pending_answer: str | None

    # Follow-up question (if evaluator decides one is needed)
    pending_follow_up: str | None

    # Number of follow-ups asked for current question
    follow_up_count: int

    # True while waiting for follow-up response
    is_follow_up: bool

    # Preserve original answer while evaluating follow-up
    initial_answer: str | None


    # --------------------------------------------------------
    # Interview History
    # --------------------------------------------------------

    qa_history: Annotated[
        list[QARound],
        operator.add
    ]

    question_count: int


    # --------------------------------------------------------
    # Session Control
    # --------------------------------------------------------

    session_complete: bool


    # --------------------------------------------------------
    # Final Report
    # --------------------------------------------------------

    final_report: dict | None