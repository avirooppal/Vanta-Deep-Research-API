import { useState, useEffect, useRef } from "react";
import { Check, Copy, Download } from "lucide-react";

interface ModeOption {
  id: string;
  name: string;
  badge: string;
  desc: string;
  defaultRounds: number;
}

const MODES: ModeOption[] = [
  {
    id: "research",
    name: "🔬 Research",
    badge: "3 Rounds",
    desc: "Balanced analytical research. Evidence gathering, contradiction check, and structured citations.",
    defaultRounds: 3,
  },
  {
    id: "study",
    name: "🎓 Study",
    badge: "2 Rounds",
    desc: "Educational mastery. First-principles Feynman explanations, practice quiz, and glossary.",
    defaultRounds: 2,
  },
  {
    id: "brief",
    name: "⚡ Brief",
    badge: "1 Round",
    desc: "Rapid executive briefing. Bottom Line Up Front (BLUF), top takeaways, and action items.",
    defaultRounds: 1,
  },
  {
    id: "deep",
    name: "🏛️ Deep",
    badge: "4 Rounds",
    desc: "Exhaustive academic dive. Rigorous literature review, arXiv whitepapers, and contradiction matrix.",
    defaultRounds: 4,
  },
];

const STAGES = [
  { id: "coord", name: "Coordinator", stageNum: "Stage 1" },
  { id: "search", name: "Search Fleet", stageNum: "Stage 2" },
  { id: "valid", name: "Validator", stageNum: "Stage 3" },
  { id: "extract", name: "Extractor", stageNum: "Stage 4" },
  { id: "conflict", name: "Contradictions", stageNum: "Stage 5" },
  { id: "synth", name: "Synthesizer", stageNum: "Stage 6" },
  { id: "verify", name: "Verifier", stageNum: "Stage 7" },
];

const API_BASE = (
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  "http://localhost:8000"
).replace(/\/$/, "");

import { CustomSelect, SelectOption } from "./ui/CustomSelect";

const PROVIDER_OPTIONS: SelectOption<string>[] = [
  { value: "", label: "Auto-detect from key" },
  { value: "openai", label: "OpenAI (GPT-4o, o3-mini)" },
  { value: "anthropic", label: "Anthropic (Claude 3.5 Sonnet)" },
  { value: "openai_compatible", label: "Gemini / Custom OpenAI Base" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "ollama", label: "Ollama / Local vLLM" },
];

const ROUNDS_OPTIONS: SelectOption<number>[] = [
  { value: 1, label: "1 Round (Fast)" },
  { value: 2, label: "2 Rounds" },
  { value: 3, label: "3 Rounds (Balanced)" },
  { value: 4, label: "4 Rounds" },
  { value: 5, label: "5 Rounds (Max)" },
];

export function ResearchConsole() {
  const [mode, setMode] = useState("research");
  const [rounds, setRounds] = useState(3);
  const [query, setQuery] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  // Execution state
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [report, setReport] = useState<{
    summary?: string;
    body_md?: string;
    citations?: any[];
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const pollRef = useRef<any>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const savedKey = localStorage.getItem("vanta_api_key") || localStorage.getItem("vanta_key");
    const savedProvider = localStorage.getItem("vanta_provider");
    const savedBaseUrl = localStorage.getItem("vanta_base_url");
    if (savedKey) setApiKey(savedKey);
    if (savedProvider) setProvider(savedProvider);
    if (savedBaseUrl) setBaseUrl(savedBaseUrl);
  }, []);

  const addLog = (msg: string) => {
    const time = new Date().toTimeString().split(" ")[0];
    setLogs((prev) => [...prev, `[${time}] ${msg}`]);
    if (terminalRef.current) {
      setTimeout(() => {
        if (terminalRef.current) {
          terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
      }, 50);
    }
  };

  const handleModeSelect = (m: ModeOption) => {
    setMode(m.id);
    setRounds(m.defaultRounds);
  };

  const saveSettings = () => {
    localStorage.setItem("vanta_api_key", apiKey.trim());
    localStorage.setItem("vanta_key", apiKey.trim());
    localStorage.setItem("vanta_provider", provider);
    localStorage.setItem("vanta_base_url", baseUrl.trim());
  };

  const launchPipeline = async () => {
    if (!query.trim()) {
      alert("Please enter a research topic or question.");
      return;
    }
    if (!apiKey.trim()) {
      setShowSettings(true);
      alert("Please provide an LLM API key (OpenAI, Anthropic, Gemini, or OpenRouter).");
      return;
    }

    saveSettings();
    setLoading(true);
    setReport(null);
    setProgress(5);
    setActiveStageIndex(0);
    setLogs([]);
    addLog(`Initializing multi-agent dispatch in [${mode.toUpperCase()}] mode...`);

    try {
      const res = await fetch(`${API_BASE}/v1/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey.trim()}`,
        },
        body: JSON.stringify({
          query: query.trim(),
          mode: mode,
          max_rounds: rounds,
          provider: provider || undefined,
          base_url: baseUrl.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || err.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      setJobId(data.id);
      addLog(`Job queued successfully: ID ${data.id}`);
      startPolling(data.id);
    } catch (err: any) {
      alert(`Launch error: ${err.message}`);
      setLoading(false);
    }
  };

  const startPolling = (id: string) => {
    let elapsed = 0;
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      elapsed += 2;
      try {
        const res = await fetch(`${API_BASE}/v1/research/${id}`, {
          headers: { Authorization: `Bearer ${apiKey.trim()}` },
        });
        if (!res.ok) return;
        const job = await res.json();

        if (job.status === "running") {
          const currentPct = Math.min(92, Math.max(15, elapsed * 5));
          setProgress(currentPct);

          if (currentPct < 25) {
            setActiveStageIndex(1);
            if (elapsed % 4 === 0) addLog("SearchAgent decomposing sub-queries & fetching web indexes...");
          } else if (currentPct < 45) {
            setActiveStageIndex(2);
            if (elapsed % 4 === 0) addLog("ValidatorAgent evaluating domain authority and source trust...");
          } else if (currentPct < 65) {
            setActiveStageIndex(3);
            if (elapsed % 4 === 0) addLog("ExtractorAgent distilling structured claims & cross-referencing memory...");
          } else if (currentPct < 80) {
            setActiveStageIndex(4);
            if (elapsed % 4 === 0) addLog("ContradictionAgent resolving factual conflicts across evidence...");
          } else {
            setActiveStageIndex(5);
            if (elapsed % 4 === 0) addLog("SynthesizerAgent compiling comprehensive report with inline citations...");
          }
        } else if (job.status === "completed") {
          clearInterval(pollRef.current);
          setProgress(100);
          setActiveStageIndex(6);
          addLog("Pipeline completed successfully! Verifying citations and finalizing output.");
          setReport(job.report || { summary: "Research completed.", body_md: job.result });
          setLoading(false);
        } else if (job.status === "failed") {
          clearInterval(pollRef.current);
          addLog(`Job failed: ${job.error || "Unknown error"}`);
          alert(`Research job failed: ${job.error || "Unknown error"}`);
          setLoading(false);
        }
      } catch (e: any) {
        console.error("Polling error:", e);
      }
    }, 2000);
  };

  const cancelJob = async () => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    try {
      await fetch(`${API_BASE}/v1/research/${jobId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${apiKey.trim()}` },
      });
      if (pollRef.current) clearInterval(pollRef.current);
      addLog("Research job cancelled by user.");
      setLoading(false);
    } catch {
      setLoading(false);
    }
  };

  const copyMarkdown = () => {
    if (!report?.body_md) return;
    navigator.clipboard.writeText(report.body_md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadMarkdown = () => {
    if (!report?.body_md) return;
    const blob = new Blob([report.body_md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vanta-${mode}-report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetConsole = () => {
    setReport(null);
    setJobId(null);
    setProgress(0);
    setLoading(false);
    setLogs([]);
  };

  return (
    <div className="w-full space-y-6">
      {/* 1. Collapsible Settings Bar (Exact Match with localhost:8000) */}
      <div className="console-card" style={{ padding: "1.25rem" }}>
        <div
          className="settings-bar"
          onClick={() => setShowSettings(!showSettings)}
        >
          <div className="settings-label">
            <span>⚙️</span>
            <span>LLM Provider &amp; API Key Configuration</span>
          </div>
          <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
            {showSettings ? "[-] Collapse" : "[+] Configure Keys"}
          </span>
        </div>

        {showSettings && (
          <div className="settings-content">
            <div className="form-group">
              <label>Provider</label>
              <CustomSelect
                options={PROVIDER_OPTIONS}
                value={provider}
                onChange={(val) => {
                  setProvider(val);
                  localStorage.setItem("vanta_provider", val);
                }}
              />
            </div>

            <div className="form-group">
              <label htmlFor="apiKey">API Key (Stored locally in browser)</label>
              <input
                type="password"
                id="apiKey"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  saveSettings();
                }}
                placeholder="sk-ant-... or sk-... or AIza..."
                className="form-input"
              />
            </div>

            <div className="form-group sm:col-span-2">
              <label htmlFor="advBaseUrl">Optional Base URL Override</label>
              <input
                type="text"
                id="advBaseUrl"
                value={baseUrl}
                onChange={(e) => {
                  setBaseUrl(e.target.value);
                  saveSettings();
                }}
                placeholder="https://api.openai.com/v1 or http://localhost:11434/v1"
                className="form-input"
              />
            </div>
          </div>
        )}
      </div>

      {/* 2. Main Query Launchpad Card (Exact Match with localhost:8000) */}
      {!loading && !report && (
        <div className="console-card" id="queryCard">
          <div className="modes-section-title">Select Research Mode</div>

          <div className="mode-grid">
            {MODES.map((m) => {
              const active = mode === m.id;
              return (
                <div
                  key={m.id}
                  onClick={() => handleModeSelect(m)}
                  className={`mode-card ${active ? "active" : ""}`}
                >
                  <div className="mode-card-header">
                    <span className="mode-icon-title">{m.name}</span>
                    <span className="mode-badge">{m.badge}</span>
                  </div>
                  <p className="mode-desc">{m.desc}</p>
                </div>
              );
            })}
          </div>

          <div className="form-group query-area">
            <label htmlFor="queryText">Research Question or Topic</label>
            <textarea
              id="queryText"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What are the key technical barriers in commercial solid-state lithium-metal batteries as of 2026?"
              className="form-textarea"
            />
            <div className="suggestions">
              <span style={{ fontSize: "0.75rem", color: "#64748b", marginRight: "0.25rem" }}>
                Try:
              </span>
              {[
                {
                  label: "Solid-state batteries",
                  text: "What are the latest breakthroughs in room-temperature solid-state batteries?",
                },
                {
                  label: "Quantum computing",
                  text: "Explain quantum computing and qubit superposition from first principles",
                },
                {
                  label: "Mamba vs Transformers",
                  text: "State space models (Mamba) vs Transformers: architectural trade-offs",
                },
              ].map((s) => (
                <span
                  key={s.label}
                  className="suggestion-pill"
                  onClick={() => setQuery(s.text)}
                >
                  {s.label}
                </span>
              ))}
            </div>
          </div>

          <div className="action-row">
            <div className="rounds-picker flex items-center gap-3">
              <label htmlFor="maxRounds" className="text-xs font-medium text-muted-foreground whitespace-nowrap">Rounds:</label>
              <CustomSelect
                options={ROUNDS_OPTIONS}
                value={rounds}
                onChange={(val) => setRounds(val)}
                className="w-48 sm:w-52"
                dropDirection="up"
              />
            </div>

            <button
              type="button"
              className="btn-primary-action"
              onClick={launchPipeline}
            >
              <span>Launch Research Fleet</span>
              <span>→</span>
            </button>
          </div>
        </div>
      )}

      {/* 3. Live Pipeline Execution Tracker Card */}
      {loading && (
        <div className="console-card">
          <div className="flex items-center justify-between border-b border-white/10 pb-5">
            <div>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
                {mode.toUpperCase()} MODE
              </span>
              <h2
                className="mt-2 text-2xl font-normal text-foreground"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                Research in Progress
              </h2>
            </div>
            <button
              type="button"
              onClick={cancelJob}
              className="rounded-full border border-white/20 bg-white/5 px-4 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
            >
              Cancel Job
            </button>
          </div>

          {/* 7 Pipeline Stages */}
          <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            {STAGES.map((s, idx) => {
              const isDone = idx < activeStageIndex;
              const isActive = idx === activeStageIndex;
              return (
                <div
                  key={s.id}
                  className={`rounded-lg border p-3 text-center transition-all ${
                    isActive
                      ? "border-white/50 bg-white/10 text-white shadow-[0_0_15px_rgba(255,255,255,0.15)]"
                      : isDone
                      ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-300"
                      : "border-white/5 bg-black/20 text-muted-foreground/60 opacity-60"
                  }`}
                >
                  <div className="text-[10px] uppercase tracking-wider">{s.stageNum}</div>
                  <div className="mt-1 text-xs font-semibold">{s.name}</div>
                </div>
              );
            })}
          </div>

          {/* Progress Track */}
          <div className="relative mt-6 h-2 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-gradient-to-r from-emerald-400 to-teal-300 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Terminal Live Logs */}
          <div
            ref={terminalRef}
            className="mt-6 max-h-48 overflow-y-auto rounded-lg border border-white/10 bg-black/60 p-4 font-mono text-xs leading-relaxed text-slate-300"
          >
            {logs.map((l, i) => (
              <div key={i} className="py-0.5">
                {l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Final Report Card */}
      {report && (
        <div className="console-card">
          <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center">
            <div>
              <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
                SYNTHESIZED REPORT
              </span>
              <h2
                className="mt-2 text-3xl font-normal sm:text-4xl"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                Research Findings
              </h2>
            </div>
            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                onClick={copyMarkdown}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy Markdown"}
              </button>
              <button
                type="button"
                onClick={downloadMarkdown}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                <Download className="size-3.5" />
                Download .md
              </button>
              <button
                type="button"
                onClick={resetConsole}
                className="rounded-full bg-white px-5 py-2 text-xs font-semibold text-black shadow-md transition-colors hover:bg-slate-200"
              >
                New Inquiry
              </button>
            </div>
          </div>

          {/* Report Content */}
          <div className="prose prose-invert mt-8 max-w-none text-slate-200">
            {report.summary && (
              <div className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-4 text-sm leading-relaxed text-muted-foreground">
                <strong className="text-foreground">Executive Summary: </strong>
                {report.summary}
              </div>
            )}
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-200">
              {report.body_md}
            </pre>
          </div>

          {/* Citations / Sources */}
          {report.citations && report.citations.length > 0 && (
            <div className="mt-8 border-t border-white/10 pt-6">
              <h3 className="mb-3 text-sm font-semibold text-foreground">Verified Sources</h3>
              <div className="flex flex-wrap gap-2">
                {report.citations.map((c: any, i: number) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-blue-300 transition-colors hover:border-white/30 hover:bg-white/10 hover:text-white"
                  >
                    {c.title || c.url}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
