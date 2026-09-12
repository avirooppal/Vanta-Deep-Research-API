import { useState, useEffect, useRef } from "react";
import { Check, Copy, Download, Clock, Layers, Globe, Sparkles, FileJson, Printer } from "lucide-react";
import { marked } from "marked";

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
  { value: "openrouter", label: "OpenRouter (Universal)" },
  { value: "openai_compatible", label: "Google Gemini (gemini-2.0-flash)" },
  { value: "groq", label: "Groq (Ultra-fast Llama-3.3, DeepSeek)" },
  { value: "deepseek", label: "DeepSeek Direct (V3 & R1)" },
  { value: "ollama", label: "Ollama Local (11434)" },
  { value: "ollama_cloud", label: "Ollama Cloud (ollama.com)" },
  { value: "mistral", label: "Mistral AI" },
  { value: "together", label: "Together AI" },
  { value: "xai", label: "xAI (Grok-2)" },
  { value: "cerebras", label: "Cerebras (Ultra-fast)" },
];

const ROUNDS_OPTIONS: SelectOption<number>[] = [
  { value: 1, label: "1 Round (Fast)" },
  { value: 2, label: "2 Rounds" },
  { value: 3, label: "3 Rounds (Balanced)" },
  { value: 4, label: "4 Rounds" },
  { value: 5, label: "5 Rounds (Max)" },
];

const MODEL_PRESETS: Record<string, string[]> = {
  openai: ["gpt-4o-mini", "gpt-4o", "o3-mini"],
  anthropic: ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
  openrouter: [
    "google/gemini-2.0-flash-001",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
  ],
  openai_compatible: ["gemini-2.0-flash", "gemini-2.5-flash-preview-05-20"],
  groq: ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "llama-3.1-8b-instant"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  ollama: ["llama3.2", "qwen2.5:7b", "deepseek-r1:8b"],
  ollama_cloud: ["llama3.3", "qwen2.5:72b", "deepseek-r1"],
  mistral: ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
  together: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
  xai: ["grok-2-latest", "grok-beta"],
  cerebras: ["llama3.3-70b", "llama3.1-8b"],
};

export function ResearchConsole() {
  const [mode, setMode] = useState("research");
  const [rounds, setRounds] = useState(3);
  const [query, setQuery] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelOverride, setModelOverride] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  // Execution state
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [finalDuration, setFinalDuration] = useState<number | null>(null);
  const [jobStats, setJobStats] = useState<any>(null);
  const [report, setReport] = useState<{
    summary?: string;
    body_md?: string;
    citations?: any[];
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const pollRef = useRef<any>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  const formatDuration = (sec: number): string => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
  };

  useEffect(() => {
    const savedKey = localStorage.getItem("vanta_api_key") || localStorage.getItem("vanta_key");
    const savedProvider = localStorage.getItem("vanta_provider");
    const savedBaseUrl = localStorage.getItem("vanta_base_url");
    const savedModel = localStorage.getItem("vanta_model_override");
    if (savedKey) setApiKey(savedKey);
    if (savedProvider) setProvider(savedProvider);
    if (savedBaseUrl) setBaseUrl(savedBaseUrl);
    if (savedModel) setModelOverride(savedModel);
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
    localStorage.setItem("vanta_model_override", modelOverride.trim());
  };

  const launchPipeline = async () => {
    if (!query.trim()) {
      alert("Please enter a research topic or question.");
      return;
    }
    if (!apiKey.trim()) {
      setShowSettings(true);
      alert("Please provide an LLM API key (OpenAI, Anthropic, Gemini, Groq, or OpenRouter).");
      return;
    }

    saveSettings();
    setLoading(true);
    setReport(null);
    setProgress(5);
    setActiveStageIndex(0);
    setLogs([]);
    setTimerSeconds(0);
    setFinalDuration(null);
    setJobStats(null);
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
          model: modelOverride.trim() || undefined,
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
      setTimerSeconds(elapsed);
      try {
        const res = await fetch(`${API_BASE}/v1/research/${id}`, {
          headers: { Authorization: `Bearer ${apiKey.trim()}` },
        });
        if (!res.ok) return;
        const job = await res.json();
        setJobStats(job);

        if (job.status === "running") {
          const currentPct = Math.min(92, Math.max(15, elapsed * 5));
          setProgress(currentPct);
          if (job.duration_seconds) setTimerSeconds(job.duration_seconds);

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
          const dur = job.duration_seconds ?? elapsed;
          setFinalDuration(dur);
          addLog(`Pipeline completed in ${formatDuration(dur)}! Verifying citations and finalizing output.`);
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

  const copyMarkdown = () => {
    if (!report?.body_md) return;
    const durStr = finalDuration ? formatDuration(finalDuration) : `${timerSeconds}s`;
    const metadataHeader = [
      `# Research Dossier: ${query}`,
      `> Mode: ${mode.toUpperCase()} | Duration: ${durStr} | Sources: ${report.citations?.length || 0} | Date: ${new Date().toLocaleDateString()}`,
      `\n---\n\n`,
    ].join("\n");
    navigator.clipboard.writeText(metadataHeader + report.body_md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadMarkdown = () => {
    if (!report?.body_md) return;
    const durStr = finalDuration ? formatDuration(finalDuration) : `${timerSeconds}s`;
    const content = [
      `# ${query}\n\n`,
      `_Generated with Vanta Deep Research in ${durStr} (${mode} mode)_\n\n`,
      report.summary ? `> **Executive Summary**: ${report.summary}\n\n` : "",
      report.body_md,
      "\n\n## Verified Sources\n",
      ...(report.citations || []).map((c: any, i: number) => `- [${i + 1}] [${c.title || c.url}](${c.url})\n`),
    ].join("");
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vanta-${mode}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportJsonDossier = () => {
    if (!report) return;
    const dossier = {
      query,
      mode,
      duration_seconds: finalDuration ?? timerSeconds,
      timestamp: new Date().toISOString(),
      model: modelOverride || provider || "default",
      summary: report.summary,
      body_md: report.body_md,
      citations: report.citations || [],
      stats: jobStats?.usage || {},
    };
    const blob = new Blob([JSON.stringify(dossier, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vanta-dossier-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const printReport = () => {
    window.print();
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

            <div className="form-group sm:col-span-2">
              <div className="flex items-center justify-between">
                <label htmlFor="advModelOverride">Model Override (Optional)</label>
                {provider === "openrouter" && (
                  <span className="text-[11px] text-amber-400/90 font-medium">Free tier limit: 20 req/min & 50 req/day</span>
                )}
              </div>
              <input
                type="text"
                id="advModelOverride"
                value={modelOverride}
                onChange={(e) => {
                  setModelOverride(e.target.value);
                  saveSettings();
                }}
                placeholder={
                  provider === "openrouter"
                    ? "e.g. google/gemini-2.0-flash-001, deepseek/deepseek-chat, or meta-llama/llama-3.3-70b-instruct"
                    : "e.g. gpt-4o, claude-3-5-sonnet-latest, or gemini-2.0-flash"
                }
                className="form-input"
              />

              {MODEL_PRESETS[provider] && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  <span className="text-[11px] text-muted-foreground font-medium mr-1">Presets:</span>
                  {MODEL_PRESETS[provider].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => {
                        setModelOverride(preset);
                        saveSettings();
                      }}
                      className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors border ${
                        modelOverride === preset
                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-semibold"
                          : "bg-white/5 hover:bg-white/10 text-muted-foreground hover:text-white border-white/10"
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              )}

              {provider === "openrouter" && (!modelOverride.trim() || modelOverride.includes("free")) && (
                <div className="mt-2.5 p-2.5 rounded-md bg-amber-500/10 border border-amber-500/30 flex items-start gap-2 text-amber-300 text-xs leading-relaxed">
                  <span className="text-amber-400 font-bold shrink-0">⚠️ Notice:</span>
                  <div>
                    <strong>Free tier rate-limit hazard:</strong> Default openrouter models (<code className="text-white bg-black/30 px-1 py-0.5 rounded">openrouter/free</code>) strictly throttle concurrent requests and may return empty findings. Click a preset chip above (e.g. <code className="text-emerald-300 bg-black/30 px-1 py-0.5 rounded">google/gemini-2.0-flash-001</code>) for fast and uninterrupted research.
                  </div>
                </div>
              )}
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
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-mono text-xs text-emerald-300">
                <Clock className="size-3 text-emerald-400 animate-spin" />
                <span>{formatDuration(timerSeconds)}</span>
              </span>
              <button
                type="button"
                onClick={cancelJob}
                className="rounded-full border border-white/20 bg-white/5 px-4 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                Cancel Job
              </button>
            </div>
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

              {/* Rich Stats Bar */}
              <div className="flex flex-wrap items-center gap-2 mt-3 pt-1 text-xs font-mono text-muted-foreground">
                <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-emerald-300">
                  <Clock className="size-3" />
                  {formatDuration(finalDuration ?? timerSeconds)}
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-white/5 border border-white/10 px-2 py-0.5 text-slate-300">
                  <Layers className="size-3 text-blue-400" />
                  {jobStats?.rounds_completed || rounds} Rounds
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-white/5 border border-white/10 px-2 py-0.5 text-cyan-300">
                  <Globe className="size-3 text-cyan-400" />
                  {report.citations?.length || 0} Sources
                </span>
                {jobStats?.usage?.tokens_in ? (
                  <span className="inline-flex items-center gap-1 rounded bg-white/5 border border-white/10 px-2 py-0.5 text-amber-300">
                    <Sparkles className="size-3 text-amber-400" />
                    {Math.round((jobStats.usage.tokens_in + jobStats.usage.tokens_out) / 1000)}k tokens
                  </span>
                ) : null}
                <span className="inline-flex items-center gap-1 rounded bg-white/5 border border-white/10 px-2 py-0.5 text-slate-400 text-[11px]">
                  {modelOverride || provider || "Default LLM"}
                </span>
              </div>
            </div>

            {/* Export Everything Suite */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={copyMarkdown}
                title="Copy full Markdown with metadata"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy Markdown"}
              </button>
              <button
                type="button"
                onClick={downloadMarkdown}
                title="Download formatted Markdown (.md) file"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                <Download className="size-3.5" />
                Download .md
              </button>
              <button
                type="button"
                onClick={exportJsonDossier}
                title="Export complete structured JSON research dossier"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                <FileJson className="size-3.5 text-amber-400" />
                Export JSON
              </button>
              <button
                type="button"
                onClick={printReport}
                title="Print or Save as PDF"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10"
              >
                <Printer className="size-3.5 text-cyan-400" />
                Print / PDF
              </button>
              <button
                type="button"
                onClick={resetConsole}
                className="rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-black shadow-md transition-colors hover:bg-slate-200"
              >
                New Inquiry
              </button>
            </div>
          </div>

          {/* Executive Summary */}
          {report.summary && (
            <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm leading-relaxed text-slate-300">
              <strong className="text-white">Executive Summary: </strong>
              {report.summary}
            </div>
          )}

          {/* Rich Rendered Markdown Content */}
          <div
            className="prose prose-invert mt-6 max-w-none text-slate-200 text-sm leading-relaxed space-y-4 [&_h1]:text-2xl [&_h1]:font-serif [&_h1]:text-white [&_h2]:text-xl [&_h2]:font-serif [&_h2]:text-white [&_h2]:mt-6 [&_h2]:mb-3 [&_h2]:border-b [&_h2]:border-white/10 [&_h2]:pb-1.5 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-white [&_h3]:mt-4 [&_h3]:mb-2 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_li]:mb-1 [&_blockquote]:border-l-2 [&_blockquote]:border-emerald-500/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-white/10 [&_th]:bg-white/5 [&_th]:p-2 [&_td]:border [&_td]:border-white/10 [&_td]:p-2 [&_a]:text-cyan-400 [&_a]:underline hover:[&_a]:text-cyan-300 [&_strong]:text-white"
            dangerouslySetInnerHTML={{ __html: marked.parse(report.body_md || "") as string }}
          />

          {/* Rich Verified Sources Gallery */}
          {report.citations && report.citations.length > 0 && (
            <div className="mt-10 border-t border-white/10 pt-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Globe className="size-4 text-cyan-400" />
                  Verified Sources ({report.citations.length})
                </h3>
                <span className="text-[11px] text-muted-foreground font-mono">Domain Authenticated</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {report.citations.map((c: any, i: number) => {
                  let domain = "";
                  try {
                    domain = new URL(c.url).hostname.replace(/^www\./, "");
                  } catch {
                    domain = "source";
                  }
                  return (
                    <a
                      key={i}
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex flex-col justify-between p-3 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] hover:border-white/20 transition-all text-left"
                    >
                      <div>
                        <div className="flex items-center justify-between text-[11px] text-cyan-400/90 font-mono mb-1">
                          <span>[{i + 1}] {domain}</span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">Trusted</span>
                        </div>
                        <p className="text-xs font-medium text-slate-200 line-clamp-2 group-hover:text-white transition-colors">
                          {c.title || c.url}
                        </p>
                      </div>
                      <span className="text-[10px] text-muted-foreground truncate mt-2 group-hover:text-cyan-300 transition-colors">
                        {c.url}
                      </span>
                    </a>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
