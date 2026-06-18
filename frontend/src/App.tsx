import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "./components/ui/button";

const videoSource =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4";

const navLinks = [
  { label: "Product", href: "#product" },
  { label: "Agents", href: "#agents" },
  { label: "Graph", href: "#graph" },
  { label: "Quick Start", href: "#quick-start" },
];

const features = [
  {
    label: "Multi-Agent Orchestration",
    title: "A fleet that challenges its own evidence.",
    body: "Search, Validate, Extract, Contradict, and Synthesize agents run multi-round loops until the research goal is satisfied.",
  },
  {
    label: "Persistent Knowledge Graph",
    title: "Every useful fact compounds.",
    body: "Extracted facts are embedded into PostgreSQL with pgvector, making prior research sessions instantly searchable.",
  },
  {
    label: "Self-Hosted Privacy",
    title: "Deep research inside your own perimeter.",
    body: "Deploy with Docker in your cloud and bring keys for OpenAI, Anthropic, Gemini, vLLM, or Ollama.",
  },
];

const deploySnippet = `git clone https://github.com/avirooppal/Vanta-Deep-Research-API
cp .env.example .env
cd Vanta-Deep-Research-API/deploy
docker compose up -d --build`;

const cliSnippet = `uv run python cli.py submit "What are the latest advancements in solid-state batteries?" \\
  --api-key "sk-..." \\
  --max-rounds 2`;

function App() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <video
        className="fixed inset-0 z-0 h-full w-full object-cover"
        src={videoSource}
        autoPlay
        loop
        muted
        playsInline
        aria-hidden="true"
      />

      <nav className="relative z-10 mx-auto flex max-w-7xl flex-row items-center justify-between px-8 py-6">
        <a
          href="#product"
          className="text-3xl tracking-tight text-foreground"
          style={{ fontFamily: "'Instrument Serif', serif" }}
        >
          Vanta
        </a>

        <div className="hidden items-center gap-9 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </div>

        <Button size="nav" onClick={() => (window.location.href = "#quick-start")}>
          Run Vanta
        </Button>
      </nav>

      <section
        id="product"
        className="relative z-10 mx-auto flex min-h-[calc(100vh-96px)] max-w-7xl flex-col items-center justify-center px-6 pb-32 pt-24 text-center"
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
            onClick={() => (window.location.href = "#quick-start")}
          >
            Quick Start
          </Button>
          <a
            href="#agents"
            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Explore the agent loop
          </a>
        </div>
      </section>

      <section
        id="agents"
        className="relative z-10 mx-auto grid max-w-7xl gap-4 px-6 pb-24 md:grid-cols-3"
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
