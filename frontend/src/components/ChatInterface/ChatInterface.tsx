import { useState, useRef, useEffect, Component } from "react";
import type { ReactNode } from "react";
import { sendChat } from "../../api/client";
import type { ChatResponse } from "../../api/client";
import { Send, Bot, User, RefreshCw, Mic, MicOff } from "lucide-react";
import { voiceService } from "../../utils/voiceService";
import { useChartColors } from "../../hooks/useTheme";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";

interface TableData {
  headers: string[];
  rows: (string | number)[][];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  chart_data?: { type: string; data: { name: string; value: number }[]; title: string } | null;
  data_table?: TableData | null;
  followups?: string[];
  originalQuestion?: string;
}

const COLORS = [
  "#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#64748b",
];

// ── Chart Error Boundary ─────────────────────────────────────────────────────

interface BoundaryProps { children: ReactNode; onError: () => void; }
interface BoundaryState { hasError: boolean; }

class ChartErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { hasError: false };

  static getDerivedStateFromError(): BoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

// ── ChatTable ────────────────────────────────────────────────────────────────

function ChatTable({ tableData }: { tableData: TableData }) {
  if (!tableData.rows || tableData.rows.length === 0) return null;
  return (
    <div className="msg-table-container">
      <table className="chat-table">
        <thead>
          <tr>
            {tableData.headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── ChatChart ────────────────────────────────────────────────────────────────

function ChatChart({ chartData }: { chartData: { type: string; data: { name: string; value: number }[]; title: string } }) {
  const cc = useChartColors();

  if (!chartData.data || chartData.data.length < 2) return null;

  const tooltipStyle = { background: cc.tooltipBg, border: `1px solid ${cc.tooltipBorder}`, borderRadius: 8 };
  const tooltipLabelStyle = { color: cc.tooltipText };
  const tooltipItemStyle = { color: cc.tooltipItem };
  const manyItems = chartData.data.length > 6;


  if (chartData.type === "line") {
    return (
      <div className="msg-chart-container">
        <h4 className="msg-chart-title">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData.data} margin={{ bottom: manyItems ? 40 : 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} />
            <XAxis
              dataKey="name"
              tick={{ fill: cc.tick, fontSize: 10 }}
              angle={manyItems ? -45 : 0}
              textAnchor={manyItems ? "end" : "middle"}
              interval={manyItems ? Math.floor(chartData.data.length / 8) : 0}
            />
            <YAxis tick={{ fill: cc.tick, fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} formatter={(v: any) => v !== undefined ? [`€${Number(v).toFixed(2)}`, "Spese"] : ["-", "Spese"]} />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#6366f1"
              strokeWidth={2}
              dot={chartData.data.length > 20 ? false : { fill: "#6366f1", r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Default: bar chart
  return (
    <div className="msg-chart-container">
      <h4 className="msg-chart-title">{chartData.title}</h4>
      <ResponsiveContainer width="100%" height={manyItems ? 280 : 250}>
        <BarChart data={chartData.data} margin={{ bottom: manyItems ? 50 : 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} />
          <XAxis
            dataKey="name"
            tick={{ fill: cc.tick, fontSize: manyItems ? 10 : 11 }}
            angle={manyItems ? -40 : 0}
            textAnchor={manyItems ? "end" : "middle"}
            interval={0}
          />
          <YAxis tick={{ fill: cc.tick, fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} formatter={(v: any) => v !== undefined ? [`€${Number(v).toFixed(2)}`, "Totale"] : ["-", "Totale"]} />
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

// ── Main Component ───────────────────────────────────────────────────────────

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [chartErrors, setChartErrors] = useState<Set<number>>(new Set());
  const [listening, setListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  
  // Singleton manages recognition


  // startRecognition rimossa: la logica è nel singleton voiceService


  const toggleVoice = () => {
    if (voiceService.isListening()) {
      voiceService.stop();
      setListening(false);
      return;
    }

    voiceService.start({
      continuous: true,
      interimResults: false,
      onResult: (transcript, isFinal) => {
        if (isFinal) setInput((prev) => prev + transcript + " ");
      },
      onError: () => {
        setListening(false);
      },
      onEnd: () => {
        setListening(false);
      }
    });

    setListening(true);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // CLEANUP PRIVACY: Assicura che il mic si spenga se l'utente cambia pagina o chiude il componente
  useEffect(() => {
    return () => {
      voiceService.stop();
    };
  }, []);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    const userMsg: Message = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await sendChat(msg, history);
      const data = res.data;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          chart_data: data.chart_data,
          data_table: data.data_table,
          followups: data.followup_questions,
          originalQuestion: msg,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Si è verificato un errore. Riprova." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const retryAsText = (question: string) => {
    handleSend(question + " Rispondi solo via testo, senza grafici o codice Python.");
  };

  const handleChartError = (msgIndex: number) => {
    setChartErrors((prev) => new Set(prev).add(msgIndex));
  };

  return (
    <div className="chat-container animate-in">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon"><Bot size={32} /></div>
            <h3>Ciao! Sono il tuo copilota finanziario</h3>
            <p>Chiedimi qualsiasi cosa sulle tue spese.</p>
            <div className="suggestions">
              {[
                "Analisi completa: dove vanno i miei soldi?",
                "Quali spese potrei tagliare per risparmiare?",
                "Top 10 transazioni più costose questo mese",
                "Confronto mese corrente vs mese precedente",
                "Distribuzione spese: weekend vs giorni feriali",
                "Statistiche riassuntive degli ultimi 30 giorni",
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

              {/* Tabella dati */}
              {msg.data_table && <ChatTable tableData={msg.data_table} />}

              {/* Grafico con error boundary */}
              {msg.chart_data && !chartErrors.has(i) && (
                <ChartErrorBoundary onError={() => handleChartError(i)}>
                  <ChatChart chartData={msg.chart_data} />
                </ChartErrorBoundary>
              )}

              {/* Fallback se grafico fallisce */}
              {msg.chart_data && chartErrors.has(i) && msg.originalQuestion && (
                <div className="chart-error-fallback">
                  <span>📊 Grafico non disponibile</span>
                  <button
                    className="btn-retry-text"
                    onClick={() => retryAsText(msg.originalQuestion!)}
                  >
                    <RefreshCw size={12} /> Riprova in testo
                  </button>
                </div>
              )}

              {msg.followups && msg.followups.length > 0 && (
                <div className="msg-followups">
                  {msg.followups.map((f, j) => (
                    <button key={j} className="followup-btn" onClick={() => handleSend(f)}>
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
          onKeyDown={(e) => e.key === "Enter" && !loading && handleSend()}
          placeholder={listening ? "Sto ascoltando..." : "Fai una domanda sulle tue spese..."}
          disabled={loading}
        />
        <button
          className={`btn-voice ${listening ? "recording" : ""}`}
          onClick={toggleVoice}
          title={listening ? "Ferma dettatura" : "Dettatura vocale"}
          disabled={loading}
        >
          {listening ? <MicOff size={16} /> : <Mic size={16} />}
        </button>
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
