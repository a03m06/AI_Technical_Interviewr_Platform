export default function Sidebar({ resumeParsed, company, difficulty, topic, questionNumber, maxQuestions }) {
  return (
    <div className="sidebar">
      <div className="sidebar-item">
        <span className="sidebar-label">Resume</span>
        <span className="sidebar-value">{resumeParsed ? "✓ Parsed" : "—"}</span>
      </div>
      <div className="sidebar-item">
        <span className="sidebar-label">Company</span>
        <span className="sidebar-value">{company || "General"}</span>
      </div>
      <div className="sidebar-item">
        <span className="sidebar-label">Difficulty</span>
        <span className="sidebar-value">{difficulty || "—"}</span>
      </div>
      <div className="sidebar-item">
        <span className="sidebar-label">Current Topic</span>
        <span className="sidebar-value">{topic || "—"}</span>
      </div>
      <div className="progress-block">
        <div className="progress-label">Question {questionNumber} / {maxQuestions}</div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${(questionNumber / maxQuestions) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}