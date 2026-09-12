import { useState, useEffect, useRef } from "react";
import {
  Check,
  Copy,
  Download,
  Clock,
  Layers,
  Globe,
  Sparkles,
  FileJson,
  Printer,
  Settings,
  X,
  Eye,
  EyeOff,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
import { marked } from "marked";
import { CustomSelect, SelectOption } from "./ui/CustomSelect";

const SCOPES = [
  { id: "research", icon: "🔬", label: "All Web (Research)", desc: "Balanced evidence & structured citations", rounds: 3 },
  { id: "study", icon: "🎓", label: "Study Deep (Feynman)", desc: "First-principles explanations & quiz", rounds: 2 },
  { id: "brief", icon: "⚡", label: "Executive Brief (BLUF)", desc: "Rapid summary & action items", rounds: 1 },
  { id: "deep", icon: "🏛️", label: "Academic Deep (Exhaustive)", desc: "Literature review & whitepapers", rounds: 4 },
];

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

const MODE_SELECT_OPTIONS: SelectOption<string>[] = [
  { value: "research", label: "🔬 Research (3 Rounds)" },
  { value: "study", label: "🎓 Study Deep (2 Rounds)" },
  { value: "brief", label: "⚡ Executive Brief (1 Round)" },
  { value: "deep", label: "🏛️ Academic Deep (4 Rounds)" },
];

const ROUNDS_OPTIONS: SelectOption<number>[] = [
  { value: 1, label: "1 Round (Fast)" },
  { value: 2, label: "2 Rounds" },
  { value: 3, label: "3 Rounds (Balanced)" },
  { value: 4, label: "4 Rounds" },
  { value: 5, label: "5 Rounds (Max)" },
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

const PROVIDER_OPTIONS: SelectOption<string>[] = [
  { value: "", label: "Auto-detect from key" },
  { value: "openai", label: "OpenAI (GPT-4o, o3-mini)" },
  { value: "anthropic", label: "Anthropic (Claude 3.5 Sonnet)" },
  { value: "openrouter", label: "OpenRouter (Universal)" },
  { value: "openai_compatible", label: "Google Gemini (gemini-2.0-flash)" },
  { value: "groq", label: "Groq (Ultra-fast Llama-3.3, DeepSeek)" },
  { value: "cerebras", label: "Cerebras (Ultra-fast 2000+ tok/s)" },
  { value: "ollama_cloud", label: "Ollama Cloud (ollama.com)" },
  { value: "deepseek", label: "DeepSeek Direct (V3 & R1)" },
  { value: "ollama", label: "Ollama Local (http://localhost:11434)" },
  { value: "mistral", label: "Mistral AI" },
  { value: "together", label: "Together AI" },
  { value: "xai", label: "xAI (Grok-2)" },
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
  cerebras: ["llama3.3-70b", "llama3.1-8b"],
  ollama_cloud: ["llama3.3", "qwen2.5:72b", "deepseek-r1"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  ollama: ["llama3.2", "qwen2.5:7b", "deepseek-r1:8b"],
  mistral: ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
  together: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
  xai: ["grok-2-latest", "grok-beta"],
};

export function ResearchConsole() {
  const [mode, setMode] = useState("research");
  const [rounds, setRounds] = useState(3);
  const [query, setQuery] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelOverride, setModelOverride] = useState("");
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [showScopeDropdown, setShowScopeDropdown] = useState(false);
  const [showRoundsDropdown, setShowRoundsDropdown] = useState(false);

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
  const timerIntervalRef = useRef<any>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scopeDropdownRef = useRef<HTMLDivElement>(null);
  const roundsDropdownRef = useRef<HTMLDivElement>(null);

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

    function handleClickOutside(e: MouseEvent) {
      if (scopeDropdownRef.current && !scopeDropdownRef.current.contains(e.target as Node)) {
        setShowScopeDropdown(false);
      }
      if (roundsDropdownRef.current && !roundsDropdownRef.current.contains(e.target as Node)) {
        setShowRoundsDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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

  const handleModeChange = (newMode: string) => {
    setMode(newMode);
    const m = MODES.find((item) => item.id === newMode);
    if (m) {
      setRounds(m.defaultRounds);
    }
  };

  const saveSettings = () => {
    localStorage.setItem("vanta_api_key", apiKey.trim());
    localStorage.setItem("vanta_key", apiKey.trim());
    localStorage.setItem("vanta_provider", provider);
    localStorage.setItem("vanta_base_url", baseUrl.trim());
    localStorage.setItem("vanta_model_override", modelOverride.trim());
  };

  const handleQueryKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      launchPipeline();
    }
  };

  const launchPipeline = async () => {
    if (!query.trim()) {
      alert("Please enter a research topic or question.");
      return;
    }
    if (!apiKey.trim()) {
      setShowSettingsModal(true);
      alert("Please provide an LLM API key in Settings (OpenAI, Anthropic, Gemini, Groq, Cerebras, etc.).");
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

    // Start live timer
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    timerIntervalRef.current = setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);

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
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
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
        setJobStats(job);

        if (job.status === "running") {
          const currentPct = Math.min(92, Math.max(15, elapsed * 5));
          setProgress(currentPct);

          if (currentPct < 25) {
            setActiveStageIndex(1);
            addLog("Executing web searches across distributed engines...");
          } else if (currentPct < 45) {
            setActiveStageIndex(2);
            addLog("Extracting raw document content and filtering noise...");
          } else if (currentPct < 65) {
            setActiveStageIndex(3);
            addLog("Cross-validating facts and checking domain authority...");
          } else if (currentPct < 80) {
            setActiveStageIndex(4);
            addLog("Analyzing contradictory claims and testing edge hypotheses...");
          } else {
            setActiveStageIndex(5);
            addLog("Synthesizing comprehensive report dossier...");
          }
        } else if (job.status === "completed") {
          clearInterval(pollRef.current);
          if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
          setProgress(100);
          setActiveStageIndex(6);
          addLog("Pipeline complete! Final report synthesized.");
          if (job.duration_seconds) setFinalDuration(job.duration_seconds);
          setReport({
            summary: job.summary,
            body_md: job.report_markdown || job.report || job.body_md || "",
            citations: job.citations || [],
          });
          setLoading(false);
        } else if (job.status === "failed") {
          clearInterval(pollRef.current);
          if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
          addLog(`Job failed: ${job.error || "Unknown execution error"}`);
          alert(`Research failed: ${job.error || "Unknown execution error"}`);
          setLoading(false);
        }
      } catch (err: any) {
        addLog(`Polling check failed: ${err.message}`);
      }
    }, 2000);
  };

  const copyMarkdown = () => {
    if (!report?.body_md) return;
    const durStr = finalDuration ? formatDuration(finalDuration) : `${timerSeconds}s`;
    const metadataHeader = [
      `# ${query}`,
      `*Generated with Vanta Deep Research in ${durStr} (${mode} mode)*`,
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
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
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
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  const currentScope = SCOPES.find((s) => s.id === mode) || SCOPES[0];

  return (
    <div className="w-full space-y-6">
      {/* ============================================================ */}
      {/* 1. Floating Input Card (Exact Match with Screenshot)          */}
      {/* ============================================================ */}
      {!loading && !report && (
        <div className="w-full space-y-3.5" id="queryCard">
          <div className="floating-input-card">
            {/* Top row: Textarea on left, Scope pill on top-right */}
            <div className="input-top-row">
              <textarea
                id="queryText"
                ref={textareaRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleQueryKeyDown}
                maxLength={2000}
                placeholder="Ask whatever you want...."
                rows={3}
              />

              {/* Scope / Mode Selector Pill */}
              <div className="scope-selector-container" ref={scopeDropdownRef}>
                <button
                  type="button"
                  onClick={() => setShowScopeDropdown(!showScopeDropdown)}
                  className="scope-pill-btn"
                >
                  <span>{currentScope.icon}</span>
                  <span>{currentScope.label}</span>
                  <ChevronDown
                    className={`size-3.5 text-muted-foreground transition-transform ${
                      showScopeDropdown ? "rotate-180" : ""
                    }`}
                  />
                </button>

                {showScopeDropdown && (
                  <div className="scope-dropdown-menu">
                    {SCOPES.map((s) => (
                      <div
                        key={s.id}
                        onClick={() => {
                          setMode(s.id);
                          setRounds(s.rounds);
                          setShowScopeDropdown(false);
                        }}
                        className={`scope-item ${mode === s.id ? "active" : ""}`}
                      >
                        <span className="text-base">{s.icon}</span>
                        <div>
                          <div className="scope-item-name">{s.label}</div>
                          <div className="scope-item-desc">{s.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Toolbar: Tools on left, Char Count + Send Arrow on right */}
            <div className="input-bottom-bar">
              <div className="input-actions-left">
                {/* Rounds Selector Pill */}
                <div className="rounds-pill-wrapper" ref={roundsDropdownRef}>
                  <button
                    type="button"
                    onClick={() => setShowRoundsDropdown(!showRoundsDropdown)}
                    className="pill-btn"
                  >
                    <Clock className="size-3.5 text-blue-400" />
                    <span>{rounds} Rounds</span>
                    <ChevronDown
                      className={`size-3 text-muted-foreground transition-transform ${
                        showRoundsDropdown ? "rotate-180" : ""
                      }`}
                    />
                  </button>

                  {showRoundsDropdown && (
                    <div className="rounds-dropdown-menu">
                      {[1, 2, 3, 4, 5].map((r) => (
                        <div
                          key={r}
                          onClick={() => {
                            setRounds(r);
                            setShowRoundsDropdown(false);
                          }}
                          className={`rounds-item ${rounds === r ? "active" : ""}`}
                        >
                          {r} {r === 1 ? "Round (Fast)" : r === 3 ? "Rounds (Balanced)" : r === 5 ? "Rounds (Max)" : "Rounds"}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Settings Pill */}
                <button
                  type="button"
                  onClick={() => setShowSettingsModal(true)}
                  className="pill-btn"
                >
                  <Settings className="size-3.5 text-indigo-400" />
                  <span>{provider ? `${provider.toUpperCase()} Settings` : "LLM Settings"}</span>
                </button>
              </div>

              <div className="input-actions-right">
                <span className="char-counter">{query.length}/2000</span>
                <button
                  type="button"
                  id="submitBtn"
                  onClick={launchPipeline}
                  disabled={loading || !query.trim()}
                  className="send-arrow-btn"
                  title="Launch Research Fleet (Enter)"
                >
                  <ArrowRight className="size-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Quick Suggestions underneath card */}
          <div className="suggestions flex flex-wrap items-center gap-2 px-1">
            <span className="text-xs text-muted-foreground mr-1">Try:</span>
            <button
              type="button"
              onClick={() => {
                setQuery("What are the latest breakthroughs in room-temperature solid-state batteries?");
                setMode("research");
                setRounds(3);
                textareaRef.current?.focus();
              }}
              className="suggestion-pill text-xs !py-1 !px-3"
            >
              Solid-state batteries
            </button>
            <button
              type="button"
              onClick={() => {
                setQuery("Explain quantum computing and qubit superposition from first principles");
                setMode("study");
                setRounds(2);
                textareaRef.current?.focus();
              }}
              className="suggestion-pill text-xs !py-1 !px-3"
            >
              Quantum computing (Study)
            </button>
            <button
              type="button"
              onClick={() => {
                setQuery("Synthesize an executive brief on EU AI Act compliance timelines and penalty caps");
                setMode("brief");
                setRounds(1);
                textareaRef.current?.focus();
              }}
              className="suggestion-pill text-xs !py-1 !px-3"
            >
              EU AI Act (Brief)
            </button>
            <button
              type="button"
              onClick={() => {
                setQuery("State space models (Mamba) vs Transformers: architectural trade-offs");
                setMode("deep");
                setRounds(4);
                textareaRef.current?.focus();
              }}
              className="suggestion-pill text-xs !py-1 !px-3"
            >
              Mamba vs Transformers (Deep)
            </button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 2. Live Pipeline Execution Tracker Card                       */}
      {/* ============================================================ */}
      {loading && (
        <div className="console-card" id="progressCard">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4 mb-4">
            <div>
              <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                {mode.toUpperCase()} MODE ACTIVE
              </span>
              <h2
                className="text-2xl font-normal sm:text-3xl text-foreground mt-0.5"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                {query || "Research in Progress"}
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 font-mono text-xs font-medium text-emerald-400">
                <Clock className="size-3 animate-spin" />
                <span>⏱️ {formatDuration(timerSeconds)}</span>
              </div>
              <button
                type="button"
                onClick={cancelJob}
                className="inline-flex items-center gap-1.5 rounded-full border border-red-500/20 bg-red-500/10 px-3 py-1 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/20 cursor-pointer"
              >
                Cancel Job
              </button>
            </div>
          </div>

          {/* 7-Stage Visual Pipeline Tracker */}
          <div className="pipeline-tracker">
            {STAGES.map((s, idx) => {
              let cls = "pending";
              if (idx < activeStageIndex) cls = "completed";
              else if (idx === activeStageIndex) cls = "active";
              return (
                <div key={s.id} className={`pipeline-stage ${cls}`}>
                  <div className="stage-num">{s.stageNum}</div>
                  <div className="stage-name">{s.name}</div>
                </div>
              );
            })}
          </div>

          {/* Animated Glowing Progress Bar */}
          <div className="progress-bar-wrap mt-4">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>

          {/* Metrics Status Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 my-4">
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Duration</span>
              <span className="text-sm font-semibold text-emerald-400 font-mono">
                {formatDuration(timerSeconds)}
              </span>
            </div>
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Searches</span>
              <span className="text-sm font-semibold text-slate-200 font-mono">
                {jobStats?.searches_count || Math.max(1, activeStageIndex * 2)}
              </span>
            </div>
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Sources</span>
              <span className="text-sm font-semibold text-cyan-400 font-mono">
                {jobStats?.citations?.length || Math.max(0, activeStageIndex * 3)}
              </span>
            </div>
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Tokens</span>
              <span className="text-sm font-semibold text-amber-400 font-mono">
                {jobStats?.usage?.tokens_in ? `${Math.round((jobStats.usage.tokens_in + jobStats.usage.tokens_out) / 1000)}k` : "Stream"}
              </span>
            </div>
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Reasoning</span>
              <span className="text-sm font-semibold text-purple-400 font-mono">
                {modelOverride || provider || "Auto"}
              </span>
            </div>
            <div className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] text-center">
              <span className="text-[10px] uppercase text-muted-foreground block">Status</span>
              <span className="text-sm font-semibold text-indigo-400 font-mono">
                {progress}%
              </span>
            </div>
          </div>

          {/* Terminal Logs */}
          <div ref={terminalRef} className="log-terminal">
            {logs.map((l, i) => (
              <div key={i}>{l}</div>
            ))}
            <div className="animate-pulse">_</div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 3. Synthesized Research Report Card                           */}
      {/* ============================================================ */}
      {report && (
        <div className="console-card" id="reportCard">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-5">
            <div>
              <span className="text-[10px] font-semibold tracking-[0.2em] text-cyan-400 uppercase">
                SYNTHESIZED REPORT &middot; {mode.toUpperCase()} MODE
              </span>
              <h2
                className="mt-2 text-3xl font-normal sm:text-4xl text-foreground"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                {query || "Research Findings"}
              </h2>

              {/* Rich Stats Bar */}
              <div className="flex flex-wrap items-center gap-2 mt-3 text-xs font-mono text-muted-foreground">
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
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10 cursor-pointer"
              >
                {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy Markdown"}
              </button>
              <button
                type="button"
                onClick={downloadMarkdown}
                title="Download formatted Markdown (.md) file"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10 cursor-pointer"
              >
                <Download className="size-3.5" />
                Download .md
              </button>
              <button
                type="button"
                onClick={exportJsonDossier}
                title="Export complete structured JSON research dossier"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10 cursor-pointer"
              >
                <FileJson className="size-3.5 text-amber-400" />
                Export JSON
              </button>
              <button
                type="button"
                onClick={printReport}
                title="Print or Save as PDF"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10 cursor-pointer"
              >
                <Printer className="size-3.5 text-cyan-400" />
                Print / PDF
              </button>
              <button
                type="button"
                onClick={resetConsole}
                className="rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-black shadow-md transition-colors hover:bg-slate-200 cursor-pointer"
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

          {/* Rendered Markdown Report */}
          <div
            className="prose prose-invert mt-6 max-w-none text-slate-200 text-sm leading-relaxed space-y-4 [&_h1]:text-2xl [&_h1]:font-serif [&_h1]:text-white [&_h2]:text-xl [&_h2]:font-serif [&_h2]:text-white [&_h2]:mt-6 [&_h2]:mb-3 [&_h2]:border-b [&_h2]:border-white/10 [&_h2]:pb-1.5 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-white [&_h3]:mt-4 [&_h3]:mb-2 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_li]:mb-1 [&_blockquote]:border-l-2 [&_blockquote]:border-emerald-500/50 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-white/10 [&_th]:bg-white/5 [&_th]:p-2 [&_td]:border [&_td]:border-white/10 [&_td]:p-2 [&_a]:text-cyan-400 [&_a]:underline hover:[&_a]:text-cyan-300 [&_strong]:text-white"
            dangerouslySetInnerHTML={{ __html: marked.parse(report.body_md || "") as string }}
          />

          {/* Verified Sources Gallery */}
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

      {/* ============================================================ */}
      {/* 4. Sleek Settings Popup Modal Dialog                         */}
      {/* ============================================================ */}
      {showSettingsModal && (
        <div
          className="settings-modal-backdrop"
          onClick={() => setShowSettingsModal(false)}
        >
          <div
            className="settings-modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="settings-modal-header">
              <div className="settings-modal-title">
                <Settings className="size-5 text-indigo-400" />
                <div>
                  <h3>LLM Provider &amp; API Key Configuration</h3>
                  <p>Choose an AI provider and enter your API key to power the multi-agent research fleet.</p>
                </div>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowSettingsModal(false)}
                title="Close"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="settings-modal-body">
              {/* Provider Selection */}
              <div className="form-group">
                <label className="text-xs font-medium text-slate-300">LLM Provider</label>
                <CustomSelect
                  options={PROVIDER_OPTIONS}
                  value={provider}
                  onChange={(val) => {
                    setProvider(val);
                    localStorage.setItem("vanta_provider", val);
                  }}
                />
              </div>

              {/* API Key with Show/Hide toggle */}
              <div className="form-group">
                <div className="flex items-center justify-between">
                  <label htmlFor="modalApiKey" className="text-xs font-medium text-slate-300">
                    API Key (Stored locally in your browser)
                  </label>
                  <span className="text-[11px] text-muted-foreground">
                    {apiKey ? "✓ Key Set" : "Required"}
                  </span>
                </div>
                <div className="relative">
                  <input
                    type={showKey ? "text" : "password"}
                    id="modalApiKey"
                    value={apiKey}
                    onChange={(e) => {
                      setApiKey(e.target.value);
                      saveSettings();
                    }}
                    placeholder={
                      provider === "groq"
                        ? "gsk_..."
                        : provider === "cerebras"
                        ? "csk-..."
                        : provider === "ollama_cloud"
                        ? "Ollama Cloud API Key..."
                        : provider === "anthropic"
                        ? "sk-ant-..."
                        : "sk-..."
                    }
                    className="form-input pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white cursor-pointer"
                  >
                    {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {/* Base URL */}
              <div className="form-group">
                <label htmlFor="modalBaseUrl" className="text-xs font-medium text-slate-300">
                  Optional Base URL Override
                </label>
                <input
                  type="text"
                  id="modalBaseUrl"
                  value={baseUrl}
                  onChange={(e) => {
                    setBaseUrl(e.target.value);
                    saveSettings();
                  }}
                  placeholder={
                    provider === "ollama"
                      ? "http://localhost:11434/v1"
                      : provider === "ollama_cloud"
                      ? "https://ollama.com/v1"
                      : "https://api.openai.com/v1"
                  }
                  className="form-input"
                />
              </div>

              {/* Model Override & Presets */}
              <div className="form-group">
                <div className="flex items-center justify-between">
                  <label htmlFor="modalModelOverride" className="text-xs font-medium text-slate-300">
                    Model Override (Optional)
                  </label>
                  {provider === "openrouter" && (
                    <span className="text-[11px] text-amber-400 font-medium">Free tier rate limited</span>
                  )}
                </div>
                <input
                  type="text"
                  id="modalModelOverride"
                  value={modelOverride}
                  onChange={(e) => {
                    setModelOverride(e.target.value);
                    saveSettings();
                  }}
                  placeholder={
                    provider === "groq"
                      ? "llama-3.3-70b-versatile"
                      : provider === "cerebras"
                      ? "llama3.3-70b"
                      : provider === "ollama_cloud"
                      ? "llama3.3"
                      : "e.g. gpt-4o or claude-3-5-sonnet-latest"
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
                        className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors border cursor-pointer ${
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
                      Default openrouter free models strictly throttle requests. Click a preset chip above (e.g. <code className="text-emerald-300 bg-black/30 px-1 py-0.5 rounded">google/gemini-2.0-flash-001</code>) for fast, uninterrupted research.
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="settings-modal-footer">
              <button
                type="button"
                onClick={() => {
                  setApiKey("");
                  setBaseUrl("");
                  setModelOverride("");
                  localStorage.removeItem("vanta_api_key");
                  localStorage.removeItem("vanta_key");
                  localStorage.removeItem("vanta_base_url");
                  localStorage.removeItem("vanta_model_override");
                }}
                className="px-3.5 py-1.5 rounded-lg border border-white/10 bg-white/5 text-xs text-muted-foreground hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              >
                Clear Settings
              </button>
              <button
                type="button"
                onClick={() => {
                  saveSettings();
                  setShowSettingsModal(false);
                }}
                className="btn-primary !py-1.5 !px-5 text-xs font-semibold cursor-pointer"
              >
                Save &amp; Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
