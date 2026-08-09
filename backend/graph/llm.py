"""
llm.py

Thin LLM wrapper used by every graph node. Two backends:

- OpenAILLM: real calls via the OpenAI API (chat.completions, JSON mode).
- MockLLM: deterministic fake responses for local testing.
"""

import os
import json
import random
import uuid

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class OpenAILLM:
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def structured_call(self, system_prompt: str, user_prompt: str) -> dict:
        resp = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )

        return json.loads(resp.choices[0].message.content)


class MockLLM:
    """
    Fake responses shaped like real ones, for local graph testing only.
    """

    def structured_call(self, system_prompt: str, user_prompt: str) -> dict:
        raise NotImplementedError(
            "MockLLM implements per-function fakes; see below."
        )


def get_backend():
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAILLM(), False
    return MockLLM(), True


_backend, _is_mock = get_backend()


# ============================================================
# Topic configuration
# ============================================================

# Topics the planner is allowed to schedule -- must match real topic strings
# in the question bank (or TOPIC_GROUP_MAP buckets in eval_store.py).
ALLOWED_TOPICS = [
    "DSA",
    "OOP",
    "System Design",
    "LLD",
    "OS",
    "DBMS",
    "SQL",
    "Python",
    "JavaScript",
    "Java",
    "Machine Learning",
    "LLM",
    "RAG",
    "Behavioral",
    "Computer Networks",
]

# crude keyword -> topic map, used by the mock backend only
KEYWORD_TOPIC_MAP = {
    "python": "Python",
    "django": "Python",
    "flask": "Python",
    "fastapi": "Python",

    "react": "JavaScript",
    "node.js": "JavaScript",
    "node": "JavaScript",
    "javascript": "JavaScript",

    "java": "Java",

    "sql": "SQL",
    "postgres": "SQL",
    "mysql": "SQL",

    "database": "DBMS",
    "dbms": "DBMS",

    "aws": "System Design",
    "docker": "System Design",
    "kubernetes": "System Design",
    "system design": "System Design",
    "scalable": "System Design",
    "microservice": "System Design",

    "rag": "RAG",
    "vector": "RAG",
    "retrieval": "RAG",

    "langchain": "LLM",
    "langgraph": "LLM",
    "llm": "LLM",
    "gpt": "LLM",
    "transformer": "LLM",

    "machine learning": "Machine Learning",
    "ml model": "Machine Learning",
    "tensorflow": "Machine Learning",

    "oop": "OOP",
    "object-oriented": "OOP",

    "operating system": "OS",

    "low-level design": "LLD",
    "lld": "LLD",

    "network": "Computer Networks",
    "tcp": "Computer Networks",
    "http": "Computer Networks",
}

# every session gets at least this much DSA + Behavioral regardless of
# resume/JD content
BASELINE_WEIGHTS = {
    "DSA": 0.20,
    "Behavioral": 0.10,
}


def _mock_topic_weights(combined_text: str) -> dict:
    text_lower = combined_text.lower()
    hits = {}

    for kw, topic in KEYWORD_TOPIC_MAP.items():
        if kw in text_lower:
            hits[topic] = hits.get(topic, 0) + 1

    weights = dict(BASELINE_WEIGHTS)

    remaining = 1.0 - sum(weights.values())

    if hits:
        total_hits = sum(hits.values())

        for topic, count in hits.items():
            weights[topic] = (
                weights.get(topic, 0)
                + remaining * (count / total_hits)
            )
    else:
        fallback = [
            "OOP",
            "System Design",
            "Behavioral",
        ]

        for topic in fallback:
            weights[topic] = (
                weights.get(topic, 0)
                + remaining / len(fallback)
            )

    total = sum(weights.values())

    return {
        topic: round(weight / total, 3)
        for topic, weight in weights.items()
    }


# ============================================================
# Resume Parsing
# ============================================================

def parse_resume(
    resume_text: str,
    job_description: str | None = None,
) -> dict:
    """
    Extracts a structured candidate profile AND topic weights
    from Resume + optional Job Description.
    """

    combined = (
        resume_text
        + ("\n\n" + job_description if job_description else "")
    )

    if _is_mock:

        text_lower = combined.lower()

        stack = [
            s
            for s in [
                "python",
                "java",
                "react",
                "node.js",
                "sql",
                "aws",
                "javascript",
            ]
            if s in text_lower
        ]

        years = 0

        for tok in resume_text.split():
            value = tok.strip(".,()")

            if value.isdigit():
                value = int(value)

                if 0 < value < 15:
                    years = value
                    break

        return {
            "years_experience": years,
            "primary_stack": stack or ["Python"],
            "strongest_topics": (
                ["DSA", "System Design"]
                if years >= 2
                else ["DSA", "OOP"]
            ),
            "target_role": "Software Engineer",
            "topic_weights": _mock_topic_weights(combined),
        }

    system = (
        "You extract a structured candidate profile from a resume and "
        "(if provided) a job description for an interview platform. "
        "Return STRICT JSON with keys:\n"
        "years_experience,\n"
        "primary_stack,\n"
        "strongest_topics,\n"
        "target_role,\n"
        "topic_weights.\n\n"
        f"topic_weights may ONLY contain these topics:\n"
        f"{', '.join(ALLOWED_TOPICS)}.\n\n"
        "Weights must sum to 1.0.\n"
        "Always include DSA >= 0.15 and Behavioral >= 0.05.\n"
        "Weight the remaining topics according to BOTH the Resume and "
        "the Job Description."
    )

    return _backend.structured_call(system, combined)
