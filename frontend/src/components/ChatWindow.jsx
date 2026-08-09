import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";

export default function ChatWindow({ messages, onSend, loading, isComplete }) {
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSubmit(e) {
    e.preventDefault();
    if (!input.trim() || loading || isComplete) return;
    onSend(input);
    setInput("");
  }

  return (
    <div className="chat-window">
      <div className="messages">
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {!isComplete && (
        <form className="chat-input-row" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your answer..."
            rows={3}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <button type="submit" disabled={loading}>
            {loading ? "..." : "Send"}
          </button>
        </form>
      )}
    </div>
  );
}