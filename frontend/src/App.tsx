import { Check, Copy, ArrowLeft } from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "./components/ui/button";
import { ResearchConsole } from "./components/ResearchConsole";

const videoSource =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4";

const features = [
  {
    label: "Multi-Agent Orchestration",
    title: "A fleet that challenges its own evidence.",
    body: "Search, Validate, Extract, Contradict, and Synthesize agents run multi-round loops until the research goal is satisfied.",
  },
  {
    label: "Adaptive Research Modes",
    title: "Study, Research, Brief, or Deep.",
    body: "Switch between Study mode (pedagogical Feynman breakdowns, quizzes, glossaries), Executive Briefs (BLUF), and Deep Academic dives.",
  },
  {
    label: "Persistent Knowledge Graph",
    title: "Every useful fact compounds.",
    body: "Extracted facts are embedded into PostgreSQL with pgvector, making prior research sessions instantly searchable.",
  },
  {
    label: "Self-Hosted Privacy",
    title: "Deep research inside your perimeter.",
    body: "Deploy with Docker in your cloud and bring keys for OpenAI, Anthropic, Gemini, vLLM, or Ollama.",
  },
];

const deploySnippet = `git clone https://github.com/avirooppal/Vanta-Deep-Research-API && \\
cd Vanta-Deep-Research-API && \\
cp .env.example .env && \\
cd deploy && \\
docker compose up -d --build`;

const cliSnippet = `uv run python cli.py submit "What are the latest advancements in solid-state batteries?" \\
  --mode study \\
  --api-key "sk-..."`;

function App() {
  const [currentPath, setCurrentPath] = useState(
    typeof window !== "undefined" ? window.location.pathname : "/"
  );

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (path: string, hash?: string) => {
    window.history.pushState({}, "", hash ? `${path}${hash}` : path);
    setCurrentPath(path);
    if (hash) {
      setTimeout(() => {
        const el = document.querySelector(hash);
        if (el) {
          el.scrollIntoView({ behavior: "smooth" });
        }
      }, 50);
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const isConsolePage = currentPath === "/console";

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#04101d] text-foreground">
      {/* Ambient Video Background matching localhost:8000 */}
      <video
        className="fixed inset-0 z-0 h-full w-full object-cover opacity-65 pointer-events-none"
        src={videoSource}
        autoPlay
        loop
        muted
        playsInline
        aria-hidden="true"
      />

      {/* Dark Radial Gradient Overlay from localhost:8000 */}
      <div
        className="fixed inset-0 z-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 20%, rgba(4, 18, 30, 0.5) 0%, rgba(2, 6, 12, 0.88) 100%)",
        }}
        aria-hidden="true"
      />

      {/* Navigation Header */}
      {isConsolePage ? (
        /* Console View Navbar: exact 1:1 match with localhost:8000 */
        <nav className="relative z-20 mx-auto flex h-20 max-w-[1100px] items-center justify-between px-6 border-b border-white/[0.08]">
          <div className="flex items-baseline gap-3">
            <a
              href="/"
              onClick={(e) => {
                e.preventDefault();
                navigate("/");
              }}
              className="text-3xl tracking-tight text-foreground transition-opacity hover:opacity-90"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              Vanta
            </a>
            <span className="rounded-full border border-white/20 bg-white/[0.03] px-2.5 py-0.5 text-[10px] font-medium tracking-[0.25em] uppercase text-muted-foreground">
              CONSOLE
            </span>
          </div>

          <div className="flex items-center gap-5 sm:gap-6">
            <span className="flex items-center text-xs text-muted-foreground">
              <span className="mr-2 inline-block size-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]" />
              Fleet Active
            </span>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              API Docs
            </a>
            <a
              href="https://github.com/avirooppal/Vanta-Deep-Research-API"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              GitHub
            </a>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-white/10 cursor-pointer"
            >
              <ArrowLeft className="size-3" />
              Overview
            </button>
          </div>
        </nav>
      ) : (
        /* Home Page Navbar: Dead-center alignment using 3-column relative/absolute layout */
        <nav className="relative z-20 mx-auto flex h-24 max-w-7xl items-center justify-between px-6 sm:px-8">
          {/* Left Brand */}
          <div className="flex flex-1 items-center justify-start">
            <a
              href="/"
              onClick={(e) => {
                e.preventDefault();
                navigate("/");
              }}
              className="text-3xl tracking-tight text-foreground transition-opacity hover:opacity-90"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              Vanta
            </a>
          </div>

          {/* Center Links: Absolutely and mathematically centered on screen */}
          <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 items-center gap-8 lg:gap-10">
            <button
              type="button"
              onClick={() => navigate("/", "#product")}
              className="cursor-pointer whitespace-nowrap text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Product
            </button>

            <button
              type="button"
              onClick={() => navigate("/console")}
              className="cursor-pointer whitespace-nowrap text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Console
            </button>

            <button
              type="button"
              onClick={() => navigate("/", "#agents")}
              className="cursor-pointer whitespace-nowrap text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Agents
            </button>

            <button
              type="button"
              onClick={() => navigate("/", "#quick-start")}
              className="cursor-pointer whitespace-nowrap text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Quick Start
            </button>
          </div>

          {/* Right Actions: FoundrList badge + Launch Console button perfectly aligned */}
          <div className="flex flex-1 items-center justify-end gap-3 sm:gap-4">
            <a
              href="https://www.foundrlist.com/product/vanta?utm_source=badge&utm_medium=embed"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center transition-opacity hover:opacity-90"
            >
              <img
                src="https://www.foundrlist.com/api/badge/vanta"
                alt="Featured on FoundrList"
                className="h-10 w-auto rounded-lg"
              />
            </a>

            <Button
              size="nav"
              className="cursor-pointer"
              onClick={() => navigate("/console")}
            >
              Launch Console
            </Button>
          </div>
        </nav>
      )}

      {/* Page Content: Console View vs Home View */}
      {isConsolePage ? (
        <div className="relative z-10 mx-auto max-w-[1180px] px-4 py-8">
          <ResearchConsole />
        </div>
      ) : (
        <>
          {/* Hero Section on Home Page */}
          <section
            id="product"
            className="relative z-10 mx-auto flex min-h-[calc(100vh-96px)] max-w-7xl flex-col items-center justify-center px-6 pb-24 pt-20 text-center"
          >
            <p className="animate-fade-rise text-sm font-medium uppercase tracking-[0.32em] text-muted-foreground">
              Privacy-first Research-as-a-Service API
            </p>

            <h1
              className="animate-fade-rise mt-8 max-w-7xl text-5xl font-normal leading-[0.95] tracking-[-2.46px] sm:text-7xl md:text-8xl"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              Autonomous research{" "}
              <em className="not-italic text-muted-foreground">without</em>{" "}
              hallucinated shortcuts.
            </h1>

            <p className="animate-fade-rise-delay mt-8 max-w-3xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              Vanta runs a multi-round agent loop inside your own infrastructure,
              building a verifiable evidence graph while keeping models, keys, and
              research data under your control.
            </p>

            <div className="animate-fade-rise-delay-2 mt-12 flex flex-col items-center gap-4 sm:flex-row">
              <Button
                size="hero"
                className="cursor-pointer"
                onClick={() => navigate("/console")}
              >
                Launch Console
              </Button>
              <button
                type="button"
                onClick={() => navigate("/", "#quick-start")}
                className="cursor-pointer text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                Quick Start & CLI
              </button>
            </div>
          </section>

          {/* Agents / Features Section */}
          <section
            id="agents"
            className="relative z-10 mx-auto grid max-w-7xl gap-4 px-6 pb-24 md:grid-cols-2 lg:grid-cols-4"
          >
            {features.map((feature) => (
              <article
                key={feature.label}
                className="liquid-glass rounded-[8px] px-6 py-7 text-left"
              >
                <p className="text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                  {feature.label}
                </p>
                <h2
                  className="mt-5 text-3xl font-normal leading-none tracking-tight text-foreground"
                  style={{ fontFamily: "'Instrument Serif', serif" }}
                >
                  {feature.title}
                </h2>
                <p className="mt-5 text-sm leading-6 text-muted-foreground">
                  {feature.body}
                </p>
              </article>
            ))}
          </section>

          {/* Evidence Graph Memory Section */}
          <section
            id="graph"
            className="relative z-10 mx-auto flex max-w-7xl flex-col gap-8 px-6 pb-24 lg:flex-row lg:items-end lg:justify-between"
          >
            <div className="max-w-3xl">
              <p className="text-sm font-medium uppercase tracking-[0.32em] text-muted-foreground">
                Evidence graph memory
              </p>
              <h2
                className="mt-6 text-5xl font-normal leading-[0.95] tracking-[-1.6px] sm:text-6xl"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                Standard LLMs forget. Vanta compounds.
              </h2>
            </div>
            <p className="max-w-md text-base leading-relaxed text-muted-foreground">
              Each extracted fact is embedded, linked, and stored globally, so teams
              can search across prior sessions instead of paying for the same
              research twice.
            </p>
          </section>

          {/* Quick Start & Deployment Section */}
          <section
            id="quick-start"
            className="relative z-10 mx-auto max-w-7xl px-6 pb-28"
          >
            <div className="liquid-glass rounded-[8px] p-5 sm:p-8 lg:p-10">
              <div className="flex flex-col gap-5 border-b border-white/10 pb-8 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-sm font-medium uppercase tracking-[0.32em] text-muted-foreground">
                    How to Run / Quick Start
                  </p>
                  <h2
                    className="mt-6 text-5xl font-normal leading-[0.95] tracking-[-1.6px] sm:text-6xl"
                    style={{ fontFamily: "'Instrument Serif', serif" }}
                  >
                    Deploy the stack. Submit a job.
                  </h2>
                </div>
                <p className="max-w-md text-sm leading-6 text-muted-foreground">
                  Vanta is designed to run from your own cloud with Docker and a
                  provider key you control. Source is available at{" "}
                  <a
                    href="https://github.com/avirooppal/Vanta-Deep-Research-API"
                    target="_blank"
                    rel="noreferrer"
                    className="text-foreground underline decoration-white/25 underline-offset-4 transition-colors hover:text-white/75"
                  >
                    avirooppal/Vanta-Deep-Research-API
                  </a>
                  .
                </p>
              </div>

              <div className="mt-8 grid gap-5 lg:grid-cols-2">
                <CodeBlock title="Deploying the Stack" code={deploySnippet} />
                <CodeBlock
                  title="Running a Research Job via CLI"
                  code={cliSnippet}
                />
              </div>
            </div>
          </section>
        </>
      )}

      {/* Floating GitHub button — bottom-left */}
      <a
        href="https://github.com/avirooppal/Vanta-Deep-Research-API"
        target="_blank"
        rel="noreferrer"
        aria-label="View Vanta on GitHub"
        className="fixed bottom-6 left-6 z-50 flex size-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-muted-foreground backdrop-blur-md transition-all duration-200 hover:scale-110 hover:border-white/20 hover:bg-white/10 hover:text-foreground"
      >
        <svg
          role="img"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
          className="size-5 fill-current"
          aria-hidden="true"
        >
          <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
        </svg>
      </a>
    </main>
  );
}

function CodeBlock({ title, code }: { title: string; code: string }) {
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <article className="rounded-[8px] border border-white/10 bg-black/35 p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-muted-foreground">
            bash
          </span>
          <button
            type="button"
            onClick={copyCode}
            className="inline-flex h-8 items-center gap-2 rounded-full border border-white/10 px-3 text-xs text-muted-foreground transition-colors hover:text-foreground"
            aria-label={`Copy ${title} command`}
          >
            {copied ? (
              <Check className="size-3.5" aria-hidden="true" />
            ) : (
              <Copy className="size-3.5" aria-hidden="true" />
            )}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <pre className="whitespace-pre-wrap break-words text-left text-[13px] leading-6 text-white/88">
        <code>{code}</code>
      </pre>
    </article>
  );
}

export default App;
