import { useState, useRef, useEffect } from "react";
import { Send, Loader, Sparkles, Wallet, Search, BarChart3, TrendingUp, RefreshCw } from "lucide-react";
import { API_URL } from "../api/client";

/** Render basic markdown: **bold**, *italic*, `code`, bullet lists, numbered lists */
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements = [];
  let listItems = [];
  let listType = null; // "ul" or "ol"

  const flushList = () => {
    if (listItems.length > 0) {
      const Tag = listType === "ol" ? "ol" : "ul";
      elements.push(
        <Tag key={`list-${elements.length}`} style={{ margin: "6px 0", paddingLeft: 20, fontSize: 14, lineHeight: 1.7 }}>
          {listItems.map((li, j) => <li key={j} style={{ marginBottom: 2 }}>{formatInline(li)}</li>)}
        </Tag>
      );
      listItems = [];
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const bulletMatch = line.match(/^[\s]*[-•*]\s+(.+)/);
    const numberMatch = line.match(/^[\s]*\d+[.)]\s+(.+)/);

    if (bulletMatch) {
      if (listType !== "ul") flushList();
      listType = "ul";
      listItems.push(bulletMatch[1]);
    } else if (numberMatch) {
      if (listType !== "ol") flushList();
      listType = "ol";
      listItems.push(numberMatch[1]);
    } else {
      flushList();
      if (line.trim() === "") {
        elements.push(<div key={`br-${i}`} style={{ height: 8 }} />);
      } else {
        elements.push(<div key={`p-${i}`} style={{ marginBottom: 2 }}>{formatInline(line)}</div>);
      }
    }
  }
  flushList();
  return <>{elements}</>;
}

function formatInline(text) {
  // Split by markdown patterns and render
  const parts = [];
  let remaining = text;
  let key = 0;

  while (remaining) {
    // **bold**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // `code`
    const codeMatch = remaining.match(/`(.+?)`/);

    // Find earliest match
    let earliest = null;
    let matchType = null;

    if (boldMatch && (!earliest || boldMatch.index < earliest.index)) {
      earliest = boldMatch;
      matchType = "bold";
    }
    if (codeMatch && (!earliest || codeMatch.index < earliest.index)) {
      earliest = codeMatch;
      matchType = "code";
    }

    if (!earliest) {
      parts.push(remaining);
      break;
    }

    // Text before match
    if (earliest.index > 0) {
      parts.push(remaining.substring(0, earliest.index));
    }

    if (matchType === "bold") {
      parts.push(<strong key={key++} style={{ color: "#e4e6f0", fontWeight: 600 }}>{earliest[1]}</strong>);
    } else if (matchType === "code") {
      parts.push(<code key={key++} style={{ background: "rgba(99,102,241,0.1)", padding: "1px 5px", borderRadius: 4, fontSize: 13, color: "#818cf8" }}>{earliest[1]}</code>);
    }

    remaining = remaining.substring(earliest.index + earliest[0].length);
  }

  return <>{parts}</>;
}

const SUGGESTIONS = [
  { text: "How much did I spend this month?", icon: BarChart3 },
  { text: "Compare my Feb vs March spending", icon: TrendingUp },
  { text: "What are my subscriptions?", icon: RefreshCw },
  { text: "Find my top food expenses", icon: Search },
];

const TOOL_LABELS = {
  search_transactions: "Searching transactions",
  get_spending_summary: "Analyzing spending",
  get_networth: "Checking finances",
  compare_periods: "Comparing periods",
  get_subscriptions: "Finding subscriptions",
};

export default function Advisor() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async (text) => {
    const msg = text || input.trim();
    if (!msg || streaming) return;

    setInput("");
    const userMsg = { role: "user", content: msg };
    const assistantMsg = { role: "assistant", content: "", tools: [] };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    const history = messages
      .filter((m) => m.role === "user" || (m.role === "assistant" && m.content))
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const token = localStorage.getItem("token");
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: msg, history }),
      });

      if (!response.ok) {
        const errText = await response.text();
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Something went wrong. Please try again.`,
          };
          return updated;
        });
        setStreaming(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);
            if (data.type === "text") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = { ...last, content: last.content + data.content };
                return updated;
              });
            } else if (data.type === "tool_use") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = { ...last, tools: [...(last.tools || []), data.name] };
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: `Connection error. Check your internet and try again.`,
        };
        return updated;
      });
    } finally {
      setStreaming(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage();
  };

  const isEmpty = messages.length === 0;

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      height: "calc(100vh - 64px)", overflow: "hidden",
    }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
        .chat-suggestion:active { transform: scale(0.98); }
      `}</style>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: "auto", padding: "16px",
        display: "flex", flexDirection: "column",
        WebkitOverflowScrolling: "touch",
      }}>
        {isEmpty ? (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: "0 8px",
          }}>
            {/* Logo */}
            <div style={{
              width: 64, height: 64, borderRadius: 20,
              background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))",
              border: "1px solid rgba(99,102,241,0.2)",
              display: "flex", alignItems: "center", justifyContent: "center",
              marginBottom: 20,
            }}>
              <Sparkles size={28} style={{ color: "#818cf8" }} />
            </div>

            <h2 style={{
              fontSize: 22, fontWeight: 700, color: "#e4e6f0",
              margin: "0 0 6px", letterSpacing: "-0.02em",
            }}>
              Ask AI
            </h2>
            <p style={{
              fontSize: 13, color: "#6b7084", textAlign: "center",
              margin: "0 0 32px", maxWidth: 280, lineHeight: 1.5,
            }}>
              Your personal finance assistant. Ask anything about your spending.
            </p>

            {/* Suggestion cards */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr",
              gap: 10, width: "100%", maxWidth: 380,
            }}>
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={s.text}
                  className="chat-suggestion"
                  onClick={() => sendMessage(s.text)}
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    borderRadius: 14,
                    padding: "16px 14px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                    display: "flex", flexDirection: "column", gap: 10,
                    minHeight: 0,
                    animation: `fadeIn 0.3s ease-out ${i * 0.05}s both`,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "rgba(99,102,241,0.3)";
                    e.currentTarget.style.background = "rgba(99,102,241,0.06)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
                    e.currentTarget.style.background = "rgba(255,255,255,0.03)";
                  }}
                >
                  <s.icon size={16} style={{ color: "#818cf8" }} />
                  <span style={{ fontSize: 12, color: "#b0b4c8", lineHeight: 1.4, fontWeight: 500 }}>
                    {s.text}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 20, paddingBottom: 8 }}>
            {messages.map((msg, i) => (
              <div key={i} style={{ animation: "fadeIn 0.2s ease-out both" }}>
                {msg.role === "user" ? (
                  /* User message — right-aligned bubble */
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <div style={{
                      background: "linear-gradient(135deg, #6366f1, #7c3aed)",
                      color: "#fff",
                      padding: "10px 16px",
                      borderRadius: "18px 18px 4px 18px",
                      fontSize: 14, lineHeight: 1.5,
                      maxWidth: "85%",
                      whiteSpace: "pre-wrap", wordBreak: "break-word",
                    }}>
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  /* AI response — full width, no bubble */
                  <div style={{ paddingLeft: 4 }}>
                    {/* Tool indicators */}
                    {msg.tools?.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                        {msg.tools.map((tool, j) => (
                          <span key={j} style={{
                            display: "inline-flex", alignItems: "center", gap: 5,
                            padding: "4px 10px", borderRadius: 8,
                            background: "rgba(99,102,241,0.06)",
                            border: "1px solid rgba(99,102,241,0.12)",
                            fontSize: 11, color: "#818cf8", fontWeight: 500,
                          }}>
                            <span style={{
                              width: 4, height: 4, borderRadius: "50%", background: "#818cf8",
                              animation: streaming && i === messages.length - 1 && !msg.content ? "pulse 1s infinite" : "none",
                            }} />
                            {TOOL_LABELS[tool] || tool}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Response text — full width with markdown */}
                    {msg.content ? (
                      <div style={{
                        fontSize: 14, lineHeight: 1.7, color: "#d1d5e0",
                        wordBreak: "break-word",
                      }}>
                        {renderMarkdown(msg.content)}
                      </div>
                    ) : (
                      streaming && i === messages.length - 1 && (
                        <div style={{ display: "flex", gap: 4, padding: "8px 0" }}>
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#6366f1", animation: "pulse 1s infinite 0s" }} />
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#6366f1", animation: "pulse 1s infinite 0.2s" }} />
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#6366f1", animation: "pulse 1s infinite 0.4s" }} />
                        </div>
                      )
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: "10px 16px",
        paddingBottom: "max(10px, env(safe-area-inset-bottom))",
        background: "#0f1117",
        borderTop: "1px solid #1e2030",
      }}>
        <form onSubmit={handleSubmit} style={{
          display: "flex", gap: 8, alignItems: "center",
          background: "#1a1d27", border: "1px solid #2d3040",
          borderRadius: 14, padding: "4px 4px 4px 16px",
        }}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your spending..."
            disabled={streaming}
            style={{
              flex: 1, background: "none", border: "none",
              color: "#e4e6f0", fontSize: 14, outline: "none",
              padding: "10px 0", minHeight: 0,
            }}
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            style={{
              width: 40, height: 40, borderRadius: 10,
              background: streaming || !input.trim() ? "#2d3040" : "linear-gradient(135deg, #6366f1, #7c3aed)",
              border: "none", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: streaming || !input.trim() ? "default" : "pointer",
              flexShrink: 0, minHeight: 0,
              transition: "all 0.15s ease",
            }}
          >
            {streaming ? (
              <Loader size={16} style={{ animation: "spin 1s linear infinite" }} />
            ) : (
              <Send size={16} />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
