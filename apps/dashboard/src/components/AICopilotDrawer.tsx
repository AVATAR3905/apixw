"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  Sparkles, 
  X, 
  Send, 
  Bot, 
  User, 
  Compass, 
  ExternalLink, 
  Key, 
  AlertCircle,
  RefreshCw,
  Tag,
  Zap,
  Clock,
  Shield
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { API_BASE } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  suggestedRoute?: string | null;
  matrixSources?: string[];
  timestamp: string;
}

interface PreMadePrompt {
  id: string;
  title: string;
  category: string;
  prompt: string;
}

export function AICopilotDrawer() {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [inputQuery, setInputQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [preMadePrompts, setPreMadePrompts] = useState<PreMadePrompt[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchPrompts() {
      try {
        const res = await fetch(`${API_BASE}/ai/pre-made-prompts`);
        if (res.ok) {
          const data = await res.json();
          setPreMadePrompts(data.prompts || []);
        }
      } catch (err) {
        console.warn("Could not fetch pre-made prompts:", err);
      }
    }
    fetchPrompts();
  }, []);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: "Welcome to the **Phoenix AI Aviation Intelligence Copilot**. I am directly grounded in our **5 authentic statistical matrices** (National Laspeyres, Carrier Inflation, Route Volatility, Lead-Time Curves, and Jet Fuel Context) with live external news context. Click a pre-made topic below or ask any question about Indian domestic airfare economics.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }
  }, [isOpen, messages.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || loading) return;

    setAuthError(null);
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInputQuery("");
    setLoading(true);

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await fetch(`${API_BASE}/ai/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: textToSend.trim(),
          conversation_history: history,
        }),
      });

      const data = await res.json();

      if (res.status === 401) {
        setAuthError(
          data.detail?.message || "OPENROUTER_API_KEY is not configured in backend environment."
        );
        const errorMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "⚠️ **Authentication Required**: This system operates on **100% cloud processing via OpenRouter**. Please configure a free OpenRouter API key in `.env` to execute live AI inference.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } else if (!res.ok) {
        throw new Error(data.detail?.message || `Gateway error (${res.status})`);
      } else {
        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.answer,
          suggestedRoute: data.suggested_route,
          matrixSources: data.matrix_sources,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `❌ **Error Connecting to OpenRouter**: ${err.message || "Failed to reach AI gateway."}`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleCorridorJump = (routeCode: string) => {
    setIsOpen(false);
    router.push(`/corridors/${routeCode}`);
  };

  return (
    <>
      {/* Floating Trigger Button on Bottom-Right */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-[18px] bg-ink px-4 py-2.5 text-xs font-sans font-medium text-paper shadow-subtle hover:bg-ink-soft transition-all group"
        title="Open Observatory AI Copilot"
      >
        <Sparkles className="h-4 w-4 text-paper" />
        <span className="tracking-wide">Ask Observatory AI</span>
      </button>

      {/* Backdrop overlay */}
      {isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 z-50 bg-black/40 transition-opacity"
        />
      )}

      {/* Sliding Drawer Container */}
      <div
        className={`fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[480px] border-l border-hairline bg-paper shadow-subtle flex flex-col transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-hairline bg-surface-alt flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-nested bg-slate-800 border border-slate-700 text-orange-400">
              <Bot className="h-4 w-4 text-orange-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs text-white font-sans tracking-tight">
                  PHOENIX AI QUANT COPILOT
                </span>
                <Badge variant="solid" size="xs">
                  OPENROUTER CLOUD
                </Badge>
              </div>
              <p className="text-[11px] text-slate-400 font-sans mt-0.5">Grounded in 5 Phoenix Econometric Matrices</p>
            </div>
          </div>

          <button
            onClick={() => setIsOpen(false)}
            className="rounded-[18px] p-1.5 text-mid-gray hover:text-ink hover:bg-canvas transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* API Key Missing Notice if Encountered */}
        {authError && (
          <div className="p-3.5 bg-red-50 border-b border-red-200 text-ember text-xs font-sans space-y-1.5 animate-in fade-in">
            <div className="flex items-center gap-1.5 font-semibold text-[12px] text-ember">
              <Key className="h-3.5 w-3.5" />
              <span>100% Cloud Processing: OpenRouter Key Required</span>
            </div>
            <p className="text-[11px] leading-tight text-mid-gray">
              Add your free OpenRouter API key to <code className="bg-canvas px-1 py-0.5 rounded text-ink border border-hairline font-mono">.env</code> as <code className="text-ember font-mono">OPENROUTER_API_KEY=sk-or-v1-...</code>.
            </p>
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] font-sans font-medium text-ink hover:underline"
            >
              Get Free Key at openrouter.ai &rarr;
            </a>
          </div>
        )}

        {/* Pre-Made Question Chips Bar */}
        <div className="p-3 border-b border-hairline bg-surface-alt overflow-x-auto no-scrollbar">
          <div className="text-[10px] uppercase tracking-wider text-mid-gray mb-1.5 px-1 font-sans font-medium">
            Suggested Inquiries:
          </div>
          <div className="flex items-center gap-1.5">
            {preMadePrompts.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSend(p.prompt)}
                disabled={loading}
                className="shrink-0 rounded-[18px] border border-hairline bg-canvas px-2.5 py-1 text-[11px] font-sans text-ink-soft hover:bg-paper hover:border-mid-gray transition-all disabled:opacity-50"
              >
                {p.title}
              </button>
            ))}
          </div>
        </div>

        {/* Chat History Scroll Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-canvas">
          {messages.map((m) => {
            const isAssistant = m.role === "assistant";
            return (
              <div
                key={m.id}
                className={`flex gap-3 ${isAssistant ? "items-start" : "items-start flex-row-reverse"}`}
              >
                <div
                  className={`h-7 w-7 rounded-[6px] flex items-center justify-center shrink-0 text-xs ${
                    isAssistant
                      ? "bg-paper border border-hairline text-ink"
                      : "bg-ink text-paper"
                  }`}
                >
                  {isAssistant ? <Bot className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
                </div>

                <div
                  className={`max-w-[85%] rounded-[18px] p-3.5 text-xs leading-relaxed space-y-2 font-sans ${
                    isAssistant
                      ? "bg-paper border border-hairline text-ink shadow-subtle"
                      : "bg-ink text-paper"
                  }`}
                >
                  <div className={`whitespace-pre-line prose prose-xs font-sans text-xs ${isAssistant ? "text-ink" : "text-paper prose-invert"}`}>
                    {m.content}
                  </div>

                  {/* Corridor Deep Link Action */}
                  {m.suggestedRoute && (
                    <div className={`pt-2 border-t flex items-center justify-between ${isAssistant ? "border-hairline" : "border-hairline/20"}`}>
                      <span className={`text-[10px] font-sans ${isAssistant ? "text-mid-gray" : "text-paper/70"}`}>Corridor Mentioned:</span>
                      <button
                        onClick={() => handleCorridorJump(m.suggestedRoute!)}
                        className={`inline-flex items-center gap-1 rounded-[18px] px-2.5 py-0.5 text-[10px] font-sans font-medium transition-colors ${
                          isAssistant
                            ? "bg-canvas border border-hairline text-ink hover:bg-surface-alt"
                            : "bg-paper/20 text-paper hover:bg-paper/30"
                        }`}
                      >
                        <span>Inspect {m.suggestedRoute}</span>
                        <ExternalLink className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  )}

                  {/* Matrix Provenance Badges */}
                  {m.matrixSources && m.matrixSources.length > 0 && (
                    <div className={`pt-1 text-[9px] font-sans flex flex-wrap gap-1 ${isAssistant ? "text-mid-gray" : "text-paper/60"}`}>
                      <span>Grounded via:</span>
                      {m.matrixSources.map((src, i) => (
                        <span key={i} className={`px-1.5 py-0.5 rounded-[18px] border ${isAssistant ? "text-mid-gray bg-canvas border-hairline" : "text-paper/80 bg-paper/10 border-paper/20"}`}>
                          {src}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className={`text-right text-[9px] font-sans ${isAssistant ? "text-mid-gray" : "text-paper/60"}`}>
                    {m.timestamp}
                  </div>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-2 text-xs font-sans text-mid-gray p-3 rounded-nested bg-paper border border-hairline w-fit shadow-subtle">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-ink" />
              <span>Analyzing matrices & synthesizing OpenRouter cloud inference...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3 border-t border-hairline bg-paper">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask anything... e.g. 'Compare IndiGo vs Air India'"
              disabled={loading}
              className="flex-1 rounded-[18px] border border-hairline bg-canvas px-3.5 py-2 text-xs font-sans text-ink placeholder:text-mid-gray focus:outline-none focus:border-ink transition-colors"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || loading}
              className="flex h-9 w-9 items-center justify-center rounded-[18px] bg-ink text-paper hover:bg-ink-soft transition-colors disabled:opacity-40 shadow-subtle"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
          <div className="mt-1.5 flex items-center justify-between text-[10px] font-sans text-mid-gray px-1">
            <span>Powered by OpenRouter Cloud Gateway</span>
            <span>Zero Price Fabrication Guardrail</span>
          </div>
        </div>
      </div>
    </>
  );
}
