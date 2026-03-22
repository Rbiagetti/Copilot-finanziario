import { useState, useRef, useEffect } from "react";
import { sendChat } from "../../api/client";
import type { ChatResponse } from "../../api/client";
import { Send, Bot, User, Sparkles } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell, PieChart, Pie, Legend,
} from "recharts";

interface Message {
  role: "user" | "assistant";
  content: string;
  chart_data?: { type: string; data: { name: string; value: number }[]; title: string } | null;
  followups?: string[];
}

const COLORS = [
  "#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#64748b",
];

function ChatChart({ chartData }: { chartData: { type: string; data: { name: string; value: number }[]; title: string } }) {
  const tooltipStyle = { background: "#1e1e2e", border: "1px solid #2a2a40", borderRadius: 8 };
  const legendStyle = { fontSize: 12, color: "#aaa" };
  // BUG-3: con molte categorie ruota le label per evitare overlap
  const manyItems = chartData.data.length > 6;

  if (chartData.type === "pie") {
    // BUG-4: usa Legend invece di label inline per evitare overlap sulle fette
    return (
      <div className="msg-chart-container">
        <h4 className="msg-chart-title">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData.data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="45%"
              outerRadius={95}
              label={false}
            >
              {chartData.data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number, _: string, props: any) => [
                `€${v.toFixed(2)} (${((props.payload.percent || 0) * 100).toFixed(0)}%)`,
                props.payload.name,
              ]}
            />
            <Legend
              wrapperStyle={legendStyle}
              formatter={(value) => <span style={{ color: "#ccc", fontSize: 12 }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartData.type === "line") {
    return (
      <div className="msg-chart-container">
        <h4 className="msg-chart-title">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData.data} margin={{ bottom: manyItems ? 40 : 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a40" />
            <XAxis
              dataKey="name"
              tick={{ fill: "#888", fontSize: 10 }}
              angle={manyItems ? -45 : 0}
              textAnchor={manyItems ? "end" : "middle"}
              interval={manyItems ? Math.floor(chartData.data.length / 8) : 0}
            />
            <YAxis tick={{ fill: "#888", fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`€${v.toFixed(2)}`, "Spese"]} />
            <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={chartData.data.length > 20 ? false : { fill: "#6366f1", r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Default: bar chart — BUG-3: ruota label se molte categorie
  return (
    <div className="msg-chart-container">
      <h4 className="msg-chart-title">{chartData.title}</h4>
      <ResponsiveContainer width="100%" height={manyItems ? 280 : 250}>
        <BarChart data={chartData.data} margin={{ bottom: manyItems ? 50 : 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a40" />
          <XAxis
            dataKey="name"
            tick={{ fill: "#888", fontSize: manyItems ? 10 : 11 }}
            angle={manyItems ? -40 : 0}
            textAnchor={manyItems ? "end" : "middle"}
            interval={0}
          />
          <YAxis tick={{ fill: "#888", fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`€${v.toFixed(2)}`, "Totale"]} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {chartData.data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
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
          chart_data: data.chart_data,
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
                "Analisi completa: dove vanno i miei soldi?",
                "Quali spese potrei tagliare per risparmiare?",
                "Trend settimanale: sto spendendo troppo?",
                "Le mie 5 spese ricorrenti piu costose",
                "Distribuzione spese: weekend vs giorni feriali",
                "Previsione: quanto spendero a fine mese?",
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
              {msg.chart_data && <ChatChart chartData={msg.chart_data} />}
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
