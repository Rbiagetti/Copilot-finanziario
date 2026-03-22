import { useState, useRef, useEffect } from "react";
import { sendChat } from "../../api/client";
import type { ChatResponse } from "../../api/client";
import { Send, Bot, User, Sparkles } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  chart?: string | null;
  followups?: string[];
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    const userMsg: Message = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await sendChat(msg, history);
      const data = res.data;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          chart: data.chart,
          followups: data.followup_questions,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Errore nella risposta AI. Riprova." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <Sparkles size={22} />
        <div>
          <h3>Chat AI Finanziaria</h3>
          <p>Fai domande sulle tue spese in linguaggio naturale</p>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <Bot size={48} />
            <h3>Ciao! Sono il tuo copilota finanziario</h3>
            <p>Chiedimi qualsiasi cosa sulle tue spese. Ecco alcuni esempi:</p>
            <div className="suggestions">
              {[
                "Quanto ho speso questo mese?",
                "Qual è la mia categoria di spesa più alta?",
                "Confronta le spese di questo mese vs il precedente",
                "In quali giorni ho speso di più?",
              ].map((s) => (
                <button key={s} className="suggestion-btn" onClick={() => handleSend(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            <div className="msg-avatar">
              {msg.role === "user" ? <User size={18} /> : <Bot size={18} />}
            </div>
            <div className="msg-content">
              <div className="msg-text" dangerouslySetInnerHTML={{
                __html: msg.content
                  .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                  .replace(/\n/g, "<br/>"),
              }} />
              {msg.chart && (
                <img
                  className="msg-chart"
                  src={`data:image/png;base64,${msg.chart}`}
                  alt="Grafico analisi"
                />
              )}
              {msg.followups && msg.followups.length > 0 && (
                <div className="msg-followups">
                  {msg.followups.map((f, j) => (
                    <button
                      key={j}
                      className="followup-btn"
                      onClick={() => handleSend(f)}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-msg assistant">
            <div className="msg-avatar"><Bot size={18} /></div>
            <div className="msg-content">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Fai una domanda sulle tue spese..."
          disabled={loading}
        />
        <button
          className="btn-send"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
