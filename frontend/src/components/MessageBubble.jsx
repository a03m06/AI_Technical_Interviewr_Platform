const DIFFICULTY_COLORS = { Easy: "#2e7d32", Medium: "#ed6c02", Hard: "#c62828" };

function ScoreBar({ label, value }) {
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${(value / 10) * 100}%` }} />
      </div>
      <span className="score-bar-value">{value.toFixed(1)}</span>
    </div>
  );
}

export default function MessageBubble({ message }) {
  const { role } = message;

  if (role === "answer") {
    return (
      <div className="bubble-row user">
        <div className="bubble user-bubble">{message.content}</div>
      </div>
    );
  }

  if (role === "feedback") {
    return (
      <div className="bubble-row assistant">
        <div className="bubble feedback-bubble-full">
          <div className="feedback-header">
            <span className="score-badge">{message.score.toFixed(1)}/10</span>
          </div>
          {message.scores && (
            <div className="score-bars">
              {Object.entries(message.scores).map(([name, val]) => (
                <ScoreBar key={name} label={name} value={val} />
              ))}
            </div>
          )}
          <p className="feedback-text">{message.content}</p>
        </div>
      </div>
    );
  }

  if (role === "report") {
    const r = message.report;
    return (
      <div className="bubble-row assistant">
        <div className="bubble report-bubble">
          <h3>Interview Complete</h3>
          <div className="overall-score">{r.overall_score} / 10</div>
          <p className="questions-asked">{r.questions_asked} questions answered</p>
          <div className="report-columns">
            <div>
              <strong>Strengths</strong>
              <ul>{r.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}</ul>
            </div>
            <div>
              <strong>Areas to Improve</strong>
              <ul>{r.areas_to_improve.map((s, i) => <li key={i}>• {s}</li>)}</ul>
            </div>
          </div>
          <p className="recommendation">{r.recommendation}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bubble-row assistant">
      <div className="bubble question-bubble">
        <div className="question-meta">
          {role === "follow_up" ? (
            <span className="follow-up-tag">Follow-up</span>
          ) : (
            <>
              <span className="progress">Q{message.questionNumber}/{message.maxQuestions}</span>
              <span className="topic-tag">{message.topic}</span>
              <span className="difficulty-tag" style={{ color: DIFFICULTY_COLORS[message.difficulty] || "#555" }}>
                {message.difficulty}
              </span>
            </>
          )}
        </div>
        <p>{message.content}</p>
      </div>
    </div>
  );
}