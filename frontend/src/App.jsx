import { useState } from "react";
import StartForm from "./components/StartForm";
import ChatWindow from "./components/ChatWindow";
import Sidebar from "./components/Sidebar";
import { startSession, submitAnswer } from "./api";
import "./App.css";

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [maxQuestions, setMaxQuestions] = useState(0);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const [sessionMeta, setSessionMeta] = useState({ company: "", difficulty: "", topic: "", questionNumber: 0 });

  function pushQuestionMessage(question, questionNumber, maxQ) {
    setMessages((prev) => [
      ...prev,
      {
        role: question.is_follow_up ? "follow_up" : "question",
        content: question.question_text,
        topic: question.topic,
        difficulty: question.difficulty,
        questionNumber,
        maxQuestions: maxQ,
      },
    ]);
    setSessionMeta((prev) => ({ ...prev, topic: question.topic, difficulty: question.difficulty, questionNumber }));
  }

  async function handleStart(params) {
    setLoading(true);
    setError(null);
    try {
      const data = await startSession(params);
      setSessionId(data.session_id);
      setMaxQuestions(data.max_questions);
      setSessionMeta((prev) => ({ ...prev, company: params.targetCompany }));
      pushQuestionMessage(data.question, data.question_number || 1, data.max_questions);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(answerText) {
    setMessages((prev) => [...prev, { role: "answer", content: answerText }]);
    setLoading(true);
    setError(null);
    try {
      const data = await submitAnswer(sessionId, answerText);

      if (data.last_result) {
        setMessages((prev) => [
          ...prev,
          {
            role: "feedback",
            content: data.last_result.feedback,
            score: data.last_result.weighted_score,
            scores: data.last_result.scores,
          },
        ]);
      }

      if (data.status === "complete") {
        setMessages((prev) => [...prev, { role: "report", report: data.final_report }]);
        setIsComplete(true);
      } else {
        pushQuestionMessage(data.question, data.question_number, maxQuestions);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      {!sessionId ? (
        <StartForm onStart={handleStart} loading={loading} error={error} />
      ) : (
        <div className="interview-layout">
          <Sidebar
            resumeParsed={true}
            company={sessionMeta.company}
            difficulty={sessionMeta.difficulty}
            topic={sessionMeta.topic}
            questionNumber={sessionMeta.questionNumber}
            maxQuestions={maxQuestions}
          />
          <div className="chat-area">
            {error && <div className="error-banner">{error}</div>}
            <ChatWindow messages={messages} onSend={handleSend} loading={loading} isComplete={isComplete} />
          </div>
        </div>
      )}
    </div>
  );
}