from fastapi import Request
from fastapi.responses import JSONResponse

# Paths that skip BYOK detection (public endpoints)
_PUBLIC_PATHS = {"/", "/console", "/health", "/health/ready", "/health/live", "/docs", "/openapi.json", "/v1/modes"}


async def auth_middleware(request: Request, call_next):
    """
    Simplified auth middleware for single-user BYOK mode.
    Detects LLM provider from the API key prefix and sets transient_backend.
    No organisation or stored API key verification.
    """
    path = request.url.path.rstrip("/")
    if path == "" or path in _PUBLIC_PATHS or request.method == "OPTIONS":
        request.state.transient_backend = None
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or invalid Authorization header. Pass your LLM API key as Bearer token."},
        )

    presented_key = auth_header.removeprefix("Bearer ").strip()

    # Auto-detect provider from key prefix
    provider = None
    base_url = None
    default_model = None

    # Known provider defaults
    PROVIDER_DEFAULTS = {
        "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "mistral": ("https://api.mistral.ai/v1", "mistral-large-latest"),
        "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        "xai": ("https://api.x.ai/v1", "grok-2-latest"),
        "cerebras": ("https://api.cerebras.ai/v1", "llama3.3-70b"),
        "ollama": ("http://localhost:11434/v1", "llama3.2"),
        "ollama_cloud": ("https://api.ollama.com/v1", "llama3.3"),
    }

    if presented_key.startswith("sk-ant-"):
        provider = "anthropic"
        base_url = "https://api.anthropic.com/v1"
        default_model = "claude-3-5-sonnet-latest"
    elif presented_key.startswith("sk-or-"):
        provider = "openrouter"
        base_url = "https://openrouter.ai/api/v1"
        default_model = "openrouter/free"
    elif presented_key.startswith("gsk_"):
        provider = "groq"
        base_url, default_model = PROVIDER_DEFAULTS["groq"]
    elif presented_key.startswith("xai-"):
        provider = "xai"
        base_url, default_model = PROVIDER_DEFAULTS["xai"]
    elif presented_key.startswith("csk-"):
        provider = "cerebras"
        base_url, default_model = PROVIDER_DEFAULTS["cerebras"]
    elif presented_key.startswith("AIza"):
        provider = "openai_compatible"
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        default_model = "gemini-2.0-flash"
    elif presented_key.startswith("sk-"):
        provider = "openai"
        base_url = "https://api.openai.com/v1"
        default_model = "gpt-4o"
    else:
        # Default fallback for local/custom tokens (e.g. ollama)
        provider = "openai_compatible"
        base_url = "http://localhost:11434/v1"
        default_model = "llama3.2"

    # Allow explicit header overrides
    provider_header = request.headers.get("X-Provider")
    base_url_header = request.headers.get("X-Base-Url")
    model_header = request.headers.get("X-Model")

    if provider_header:
        provider = provider_header.lower()
        if provider in PROVIDER_DEFAULTS and not base_url_header:
            base_url, def_mod = PROVIDER_DEFAULTS[provider]
            if not model_header:
                default_model = def_mod
    if base_url_header:
        base_url = base_url_header
    if model_header:
        default_model = model_header

    if not provider:
        return JSONResponse(
            status_code=401,
            content={"error": "Could not detect LLM provider from your API key. Use X-Provider header to specify."},
        )

    request.state.transient_backend = {
        "provider": provider,
        "api_key": presented_key,
        "base_url": base_url,
        "model": default_model,
    }

    return await call_next(request)
