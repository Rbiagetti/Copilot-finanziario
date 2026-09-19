import { useState, useRef, useEffect, Component } from "react";
import type { ReactNode } from "react";
import { sendChat } from "../../api/client";
import type { ChatResponse } from "../../api/client";
import { Send, Bot, User, RefreshCw, Mic, MicOff } from "lucide-react";
import { voiceService } from "../../utils/voiceService";
import { useChartColors } from "../../hooks/useTheme";
import { CATEGORY_COLOR } from "../../lib/categoryIcons";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";

interface TableData {
  headers: string[];
  rows: (string | number)[][];
}

interface ReasoningStep {
  phase: string;
  label: string;
  detail: string;
  duration_ms: number;
  status: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  chart_data?: { type: string; data: { name: string; value: number }[]; title: string } | null;
  data_table?: TableData | null;
  followups?: string[];
  originalQuestion?: string;
  reasoning_steps?: ReasoningStep[];
}

// Sequenza di fallback (tinte di CATEGORY_COLOR) per barre che non corrispondono a una categoria
const FALLBACK_COLORS = [
  CATEGORY_COLOR.cibo, CATEGORY_COLOR.trasporti, CATEGORY_COLOR.casa,
  CATEGORY_COLOR.svago, CATEGORY_COLOR.lavoro, CATEGORY_COLOR.formazione,
];

// C-2: Escape HTML prima di applicare qualunque formatting — previene XSS
function escapeHtml(raw: string): string {
  const div = document.createElement("div");
  div.textContent = raw;
  return div.innerHTML;
}

// Markdown-lite: bold, elenchi puntati/numerati raggruppati in <ul>/<ol>, paragrafi separati.
// Input già passato attraverso escapeHtml, quindi è sicuro inserire i tag generati qui.
function formatMarkdownLite(content: string): string {
  const escaped = escapeHtml(content);

  // Guardia: se "**" compare un numero dispari di volte (bold non chiuso dal modello),
  // rimuove l'ultima occorrenza per evitare di mostrare asterischi grezzi in UI.
  const starCount = (escaped.match(/\*\*/g) || []).length;
  const safe = starCount % 2 === 1
    ? (() => {
        const idx = escaped.lastIndexOf("**");
        return escaped.slice(0, idx) + escaped.slice(idx + 2);
      })()
    : escaped;

  const withInline = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  const lines = withInline.split("\n");
  const htmlBlocks: string[] = [];
  let listBuffer: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const flushList = () => {
    if (listBuffer.length > 0 && listType) {
      htmlBlocks.push(`<${listType}>${listBuffer.map((li) => `<li>${li}</li>`).join("")}</${listType}>`);
      listBuffer = [];
      listType = null;
    }
  };

  let paraBuffer: string[] = [];
  const flushPara = () => {
    if (paraBuffer.length > 0) {
      htmlBlocks.push(`<p>${paraBuffer.join("<br/>")}</p>`);
      paraBuffer = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    // Accetta bullet "- ", "* ", "• " ed elenchi numerati "1. " / "1) "
    const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
    const numberedMatch = line.match(/^\d+[.)]\s+(.*)$/);

    if (bulletMatch || numberedMatch) {
      flushPara();
      const nextType: "ul" | "ol" = bulletMatch ? "ul" : "ol";
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listBuffer.push((bulletMatch ?? numberedMatch)![1]);
    } else if (line === "") {
      flushList();
      flushPara();
    } else {
      flushList();
      paraBuffer.push(line);
    }
  }
  flushList();
  flushPara();

  return htmlBlocks.join("");
}

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

  const tooltipStyle = { background: cc.tooltipBg, border: `1px solid ${cc.tooltipBorder}`, borderRadius: 0 };
  const tooltipLabelStyle = { color: cc.tooltipText };
  const tooltipItemStyle = { color: cc.tooltipItem };
  const manyItems = chartData.data.length > 6;


  if (chartData.type === "line") {
    return (
      <div className="msg-chart-container">
        <h4 className="msg-chart-title">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart accessibilityLayer={false} data={chartData.data} margin={{ bottom: manyItems ? 40 : 5 }}>
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
              stroke="#ffffff"
              strokeWidth={2}
              dot={chartData.data.length > 20 ? false : { fill: "#ffffff", r: 2 }}
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
        <BarChart accessibilityLayer={false} data={chartData.data} margin={{ bottom: manyItems ? 50 : 5 }}>
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
          <Bar dataKey="value" radius={[0, 0, 0, 0]}>
            {chartData.data.map((d, i) => (
              <Cell
                key={i}
                fill={CATEGORY_COLOR[d.name?.toString().toLowerCase()] ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── ThinkingTrace ────────────────────────────────────────────────────────────

const PHASE_TAG: Record<string, string> = {
  pre_filter:    "filter",
  macro_match:   "macro",
  llm_router:    "router",
  fn_execute:    "exec",
  llm_interpret: "llm",
  text_answer:   "llm",
};

// Strip leading emoji / unicode symbols from backend labels
function cleanLabel(label: string): string {
  return label.replace(/^[\p{Emoji}\p{So}\p{Sk}✓⛔–•]+\s*/u, "").trim();
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function ThinkingTrace({ steps }: { steps?: ReasoningStep[] }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;
  const totalMs = steps.reduce((s, x) => s + x.duration_ms, 0);
  const llmSteps = steps.filter(s => s.phase === "llm_router" || s.phase === "llm_interpret" || s.phase === "text_answer").length;
  return (
    <div className="tt-trace">
      <button
        className="tt-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="tt-dot" />
        <span className="tt-label">
          {steps.length} steps · {fmtMs(totalMs)}
          {llmSteps > 0 && <span className="tt-llm-badge">{llmSteps} LLM</span>}
        </span>
        <span className="tt-chevron">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="tt-steps">
          {steps.map((step, i) => (
            <div key={i} className={`tt-step tt-step--${step.status}`}>
              <span className={`tt-phase tt-phase--${step.phase}`}>
                {PHASE_TAG[step.phase] ?? step.phase}
              </span>
              <span className="tt-step-label">{cleanLabel(step.label)}</span>
              {step.detail && (
                <span className="tt-step-detail">{step.detail}</span>
              )}
              <span className="tt-step-ms">{fmtMs(step.duration_ms)}</span>
            </div>
          ))}
        </div>
      )}
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

  // MOBILE KEYBOARD: .chat-input è ancorato con bottom:Npx dentro .chat-container fixed
  // (vedi chat.css) — cioè al viewport di LAYOUT, non a quello VISIVO. Quando si apre la
  // tastiera su iOS/Android il layout viewport non cambia, quindi il pannello di input resta
  // dov'era e la tastiera ci si sovrappone sopra, nascondendolo. visualViewport.height invece
  // si riduce quando la tastiera appare: usiamo la differenza per spingere il pannello sopra
  // la tastiera via custom property, letta da chat.css solo nella media query mobile.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const root = document.documentElement;
    const update = () => {
      // Solo mentre l'input della chat ha il focus: un cambio del visual viewport senza
      // tastiera (es. iOS che sposta la vista dopo un tocco su un elemento focusabile) non
      // deve spostare il pannello, altrimenti sembra che lo scroll si "blocchi".
      const typing = !!document.activeElement?.closest?.(".chat-input");
      const inset = typing ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
      root.style.setProperty("--kb-inset", `${inset}px`);
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      root.style.removeProperty("--kb-inset");
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
      // B-1: tronca history agli ultimi 20 messaggi — evita payload crescenti e costi LLM
      const history = messages.slice(-20).map((m) => ({ role: m.role, content: m.content }));
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
          reasoning_steps: data.reasoning_steps,
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
                "Dove vanno i miei soldi questo mese?",
                "Quali spese potrei tagliare?",
                "Confronto con il mese scorso",
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
              {msg.role === "assistant" && (
                <ThinkingTrace steps={msg.reasoning_steps} />
              )}
              <div className="msg-text" dangerouslySetInnerHTML={{
                __html: formatMarkdownLite(msg.content),
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
          placeholder={listening ? "Sto ascoltando..." : ""}
          disabled={loading}
        />
        <button
          className={`btn-voice ${listening ? "recording" : ""}`}
          onClick={toggleVoice}
          title={listening ? "Ferma dettatura" : "Dettatura vocale"}
          aria-label={listening ? "Ferma dettatura vocale" : "Avvia dettatura vocale"}
          disabled={loading}
        >
          {listening ? <MicOff size={16} /> : <Mic size={16} />}
        </button>
        <button
          className="btn-send"
          onClick={() => handleSend()}
          aria-label="Invia messaggio"
          disabled={loading || !input.trim()}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
