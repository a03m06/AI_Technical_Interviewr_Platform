import { useState } from "react";
import { extractPdfText } from "../utils/extractPdfText";

const COMPANIES = ["General (no specific company)", "Amazon", "Google", "Microsoft", "Meta", "Accenture", "Cisco", "Zoho", "Razorpay", "Other"];
const INTERVIEW_TYPES = ["Mixed", "DSA", "AI/ML", "Backend", "Frontend"];
const DIFFICULTIES = ["Easy", "Medium", "Hard"];

export default function StartForm({ onStart, loading, error }) {
  const [inputMode, setInputMode] = useState("paste"); // "paste" | "upload"
  const [resumeText, setResumeText] = useState("");
  const [fileName, setFileName] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [jobDescription, setJobDescription] = useState("");
  const [maxQuestions, setMaxQuestions] = useState(5);
  const [company, setCompany] = useState(COMPANIES[0]);
  const [customCompany, setCustomCompany] = useState("");
  const [interviewType, setInterviewType] = useState("Mixed");
  const [difficulty, setDifficulty] = useState("Medium");

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setFileName(file.name);
    setExtracting(true);
    try {
      const text = await extractPdfText(file);
      setResumeText(text);
    } catch (err) {
      alert("Couldn't read that PDF. Try pasting the text instead.");
      setFileName(null);
    } finally {
      setExtracting(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!resumeText.trim()) return;
    const resolvedCompany = company === "Other" ? customCompany : company;
    onStart({
      resumeText,
      jobDescription,
      maxQuestions: Number(maxQuestions),
      targetCompany: resolvedCompany.startsWith("General") ? "" : resolvedCompany,
      interviewType,
      difficulty,
    });
  }

  return (
    <div className="start-form">
      <h1>AI Technical Interviewer</h1>
      <p className="subtitle">
        Practice technical interviews tailored to your resume and target role — AI-generated
        questions, adaptive follow-ups, and detailed feedback.
      </p>

      <div className="feature-cards">
        <div className="feature-card">📄 Resume-based Questions</div>
        <div className="feature-card">🧠 Adaptive Follow-ups</div>
        <div className="feature-card">📊 Detailed Performance Analysis</div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="input-mode-toggle">
          <button type="button" className={inputMode === "paste" ? "active" : ""} onClick={() => setInputMode("paste")}>
            Paste Resume Text
          </button>
          <button type="button" className={inputMode === "upload" ? "active" : ""} onClick={() => setInputMode("upload")}>
            📄 Upload PDF
          </button>
        </div>

        {inputMode === "upload" ? (
          <label className="file-drop">
            {extracting ? "Extracting text..." : fileName ? `✓ ${fileName} (${resumeText.split(/\s+/).length} words extracted)` : "Click to choose a PDF resume"}
            <input type="file" accept="application/pdf" onChange={handleFileChange} hidden />
          </label>
        ) : (
          <label>
            Resume text
            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste your resume text here..."
              rows={7}
              required
            />
          </label>
        )}

        <label>
          Job description (optional — weights questions toward the skills it mentions)
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description here..."
            rows={4}
          />
        </label>

        <div className="form-row">
          <label>
            Company
            <select value={company} onChange={(e) => setCompany(e.target.value)}>
              {COMPANIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          {company === "Other" && (
            <label>
              Company name
              <input type="text" value={customCompany} onChange={(e) => setCustomCompany(e.target.value)} />
            </label>
          )}
        </div>

        <div className="form-row">
          <label>
            Interview type
            <select value={interviewType} onChange={(e) => setInterviewType(e.target.value)}>
              {INTERVIEW_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>
            Difficulty
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label>
            Questions
            <input type="number" min={1} max={20} value={maxQuestions} onChange={(e) => setMaxQuestions(e.target.value)} />
          </label>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button type="submit" disabled={loading || extracting}>
          {loading ? "Starting..." : "🚀 Start Mock Interview"}
        </button>
      </form>
    </div>
  );
}