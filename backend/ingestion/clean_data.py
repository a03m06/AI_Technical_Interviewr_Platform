"""
clean_data.py
Normalizes the raw interview_question_bank_final.json into a consistent
schema ready for embedding + ingestion into the RAG vector store.

Fixes applied:
- question_type casing/aliases collapsed to a fixed vocabulary
  (Lld -> LLD, Hld -> HLD, "System Design" type merged with Design, etc.)
- difficulty casing normalized to {Easy, Medium, Hard}
- topic casing normalized (title case, trimmed)
- company casing normalized, "General" kept as an explicit no-company marker
- tags: lowercased, deduped, stripped
- year: kept as int or None
- adds a `search_text` field: the concatenation of fields that will be
  embedded, so the embedding step doesn't need to know the schema
"""

import json
import re
from pathlib import Path
from collections import Counter

RAW_PATH = Path(__file__).parent.parent / "data" / "interview_question_bank_final.json"
OUT_PATH = Path(__file__).parent.parent / "data" / "questions_clean.json"

# question_type values that are really the same bucket, collapsed here
QUESTION_TYPE_MAP = {
    "theory": "Theory",
    "coding": "Coding",
    "design": "Design",
    "lld": "Design",
    "hld": "Design",
    "system design": "Design",
    "behavioral": "Behavioral",
    "conceptual": "Theory",
    "comparative": "Theory",
    "comparison": "Theory",
    "practical": "Coding",
    "troubleshooting": "Theory",
    "scenario": "Behavioral",
    "decision making": "Behavioral",
    "api design": "Design",
    "applied": "Coding",
}

DIFFICULTY_MAP = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}


def normalize_str(s):
    if s is None:
        return None
    return re.sub(r"\s+", " ", s).strip()


def normalize_question_type(raw):
    if not raw:
        return "Theory"
    key = raw.strip().lower()
    return QUESTION_TYPE_MAP.get(key, normalize_str(raw).title())


def normalize_difficulty(raw):
    if not raw:
        return "Medium"
    key = raw.strip().lower()
    return DIFFICULTY_MAP.get(key, "Medium")


def normalize_topic(raw):
    if not raw:
        return "General"
    t = normalize_str(raw)
    # keep known acronyms upper-cased
    acronym_fix = {
        "Dsa": "DSA", "Lld": "LLD", "Hld": "HLD", "Os": "OS", "Sql": "SQL",
        "Dbms": "DBMS", "Ai": "AI", "Llm": "LLM", "Oop": "OOP",
    }
    return acronym_fix.get(t, t)


def normalize_company(raw):
    if not raw:
        return "General"
    return normalize_str(raw)


def normalize_tags(raw_tags):
    if not raw_tags:
        return []
    cleaned = {normalize_str(t).lower() for t in raw_tags if t and normalize_str(t)}
    return sorted(cleaned)


def normalize_year(raw):
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def build_search_text(item):
    """Text that will actually get embedded — question + light context."""
    parts = [
        item["question_text"],
        f"Topic: {item['topic']}",
        f"Type: {item['question_type']}",
        f"Difficulty: {item['difficulty']}",
    ]
    if item["tags"]:
        parts.append("Tags: " + ", ".join(item["tags"]))
    if item["company"] != "General":
        parts.append(f"Asked at: {item['company']}")
    return " | ".join(parts)


def clean(raw_items):
    cleaned = []
    seen_text = set()
    dupes = 0
    for item in raw_items:
        q_text = normalize_str(item.get("question_text"))
        if not q_text:
            continue

        dedupe_key = (q_text.lower(), normalize_company(item.get("company")))
        if dedupe_key in seen_text:
            dupes += 1
            continue
        seen_text.add(dedupe_key)

        rec = {
            "id": item.get("id"),
            "company": normalize_company(item.get("company")),
            "role": normalize_str(item.get("role")) or "Software Engineer",
            "topic": normalize_topic(item.get("topic")),
            "difficulty": normalize_difficulty(item.get("difficulty")),
            "question_type": normalize_question_type(item.get("question_type")),
            "question_text": q_text,
            "tags": normalize_tags(item.get("tags")),
            "year": normalize_year(item.get("year")),
        }
        rec["search_text"] = build_search_text(rec)
        cleaned.append(rec)

    return cleaned, dupes


def main():
    raw = json.loads(RAW_PATH.read_text())
    cleaned, dupes = clean(raw)

    OUT_PATH.write_text(json.dumps(cleaned, indent=2))

    print(f"Input records:   {len(raw)}")
    print(f"Output records:  {len(cleaned)}")
    print(f"Duplicates removed: {dupes}")
    print()
    print("Topic distribution:")
    for topic, count in Counter(r["topic"] for r in cleaned).most_common():
        print(f"  {topic:20s} {count}")
    print()
    print("Question type distribution:")
    for qt, count in Counter(r["question_type"] for r in cleaned).most_common():
        print(f"  {qt:20s} {count}")
    print()
    print(f"Wrote cleaned data to {OUT_PATH}")


if __name__ == "__main__":
    main()
