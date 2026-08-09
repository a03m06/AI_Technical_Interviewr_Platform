const BASE_URL = "http://localhost:8000";

async function handleResponse(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function startSession({
  resumeText,
  jobDescription,
  maxQuestions,
  targetCompany,
}) {
  const res = await fetch(`${BASE_URL}/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resume_text: resumeText,
      job_description: jobDescription || null,
      max_questions: maxQuestions || null,
      target_company: targetCompany || null,
    }),
  });

  return handleResponse(res);
}

export async function submitAnswer(sessionId, answer) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });

  return handleResponse(res);
}