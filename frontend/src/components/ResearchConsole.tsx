import { useState, useEffect, useRef } from "react";
import { Check, Copy, Download, Loader2, ArrowRight, X } from "lucide-react";

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
      <div className="liquid-glass rounded-xl p-4 sm:p-5 transition-all">
        <div
          className="flex cursor-pointer select-none items-center justify-between"
          onClick={() => setShowSettings(!showSettings)}
        >
          <div className="flex items-center gap-2.5 text-sm font-medium text-foreground">
            <span>⚙️</span>
            <span>LLM Provider &amp; API Key Configuration</span>
          </div>
          <span className="text-xs text-muted-foreground transition-colors hover:text-foreground">
            {showSettings ? "[-] Collapse" : "[+] Configure Keys"}
          </span>
        </div>

        {showSettings && (
          <div className="mt-4 grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-muted-foreground">Provider</label>
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  saveSettings();
                }}
                className="w-full rounded-lg border border-white/15 bg-black/60 px-3 py-2.5 text-sm text-foreground outline-none transition-colors focus:border-white/40"
              >
                <option value="">Auto-detect from key</option>
                <option value="openai">OpenAI (GPT-4o, o3-mini)</option>
                <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                <option value="openai_compatible">Gemini / Custom OpenAI Base</option>
                <option value="openrouter">OpenRouter</option>
                <option value="ollama">Ollama / Local vLLM</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                API Key (Stored locally in browser)
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  saveSettings();
                }}
                placeholder="sk-ant-... or sk-... or AIza..."
                className="w-full rounded-lg border border-white/15 bg-black/60 px-3 py-2.5 text-sm text-foreground outline-none transition-colors focus:border-white/40"
              />
            </div>

            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">
                Optional Base URL Override
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => {
                  setBaseUrl(e.target.value);
                  saveSettings();
                }}
                placeholder="https://api.openai.com/v1 or http://localhost:11434/v1"
                className="w-full rounded-lg border border-white/15 bg-black/60 px-3 py-2.5 text-sm text-foreground outline-none transition-colors focus:border-white/40"
              />
            </div>
          </div>
        )}
      </div>

      {/* 2. Main Query Launchpad Card */}
      {!loading && !report && (
        <div className="liquid-glass rounded-xl p-6 sm:p-8">
          <div className="mb-3.5 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Select Research Mode
          </div>

          {/* Mode Tiles */}
          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {MODES.map((m) => {
              const active = mode === m.id;
              return (
                <div
                  key={m.id}
                  onClick={() => handleModeSelect(m)}
                  className={`flex cursor-pointer flex-col justify-between rounded-xl border p-4.5 text-left transition-all ${
                    active
                      ? "border-white/60 bg-white/10 shadow-[0_0_20px_rgba(255,255,255,0.06),0_8px_24px_rgba(0,0,0,0.4)]"
                      : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">{m.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        active ? "bg-white text-black" : "bg-white/10 text-muted-foreground"
                      }`}
                    >
                      {m.badge}
                    </span>
                  </div>
                  <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">{m.desc}</p>
                </div>
              );
            })}
          </div>

          {/* Query Input */}
          <div className="mt-8 flex flex-col gap-2">
            <label className="text-xs font-medium text-muted-foreground">
              Research Question or Topic
            </label>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={4}
              placeholder="What are the key technical barriers in commercial solid-state lithium-metal batteries as of 2026?"
              className="w-full rounded-xl border border-white/15 bg-black/50 p-4 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-white/40"
            />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground/80">Try:</span>
              {[
                { label: "Solid-state batteries", text: "What are the latest breakthroughs in room-temperature solid-state batteries?" },
                { label: "Quantum computing", text: "Explain quantum computing and qubit superposition from first principles" },
                { label: "Mamba vs Transformers", text: "State space models (Mamba) vs Transformers: architectural trade-offs" },
              ].map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => setQuery(s.text)}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-muted-foreground transition-all hover:border-white/25 hover:bg-white/[0.08] hover:text-foreground"
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Action Row */}
          <div className="mt-8 flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-3">
              <label className="text-xs font-medium text-muted-foreground">Rounds:</label>
              <select
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
                className="rounded-lg border border-white/15 bg-black/60 px-3.5 py-2 text-sm text-foreground outline-none transition-colors focus:border-white/40"
              >
                <option value={1}>1 Round (Fast)</option>
                <option value={2}>2 Rounds</option>
                <option value={3}>3 Rounds (Balanced)</option>
                <option value={4}>4 Rounds</option>
                <option value={5}>5 Rounds (Max)</option>
              </select>
            </div>

            <button
              type="button"
              onClick={launchPipeline}
              className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-semibold text-black shadow-[0_4px_20px_rgba(255,255,255,0.25)] transition-all hover:bg-slate-100 hover:shadow-[0_8px_30px_rgba(255,255,255,0.35)]"
            >
              <span>Launch Research Fleet</span>
              <ArrowRight className="size-4" />
            </button>
          </div>
        </div>
      )}

      {/* 3. Live Pipeline Execution Tracker Card */}
      {loading && (
        <div className="liquid-glass rounded-xl p-6 sm:p-8">
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
        <div className="liquid-glass rounded-xl p-6 sm:p-10">
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
