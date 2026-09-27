# Vanta Security & Privacy Architecture

Vanta is engineered with a **zero-trust, privacy-first perimeter**:

---

## 1. Zero-Trust In-Memory Credential Broker

- **Bring Your Own Key (BYOK)**: Clients submit their own LLM API keys via the `Authorization: Bearer` header.
- **Ephemeral In-Memory Isolation**: Keys are never logged or stored in plain text.
- **Fernet Encryption at Rest**: When stored with background job records in PostgreSQL, credentials are encrypted using AES-128-CBC + HMAC-SHA256 authenticated symmetric encryption via `cryptography.fernet`.
- **Automatic Key Provider Detection**: Keys (`sk-...`, `sk-ant-...`, `AIza...`, `gsk_...`, `csk-...`) are detected automatically without exposing provider information.

---

## 2. Sentinel Content Sanitization

Before extracted web text is injected into LLM context:
- Content is cleaned of suspicious prompt injection delimiters.
- Text is wrapped inside semantic markdown security boundaries.
- Provenance tracking tags every claim with a SHA-256 hash of the origin content.

---

## 3. Append-Only Audit Logging

Every incoming HTTP request generates an immutable audit record in the `audit_log` table:
- Captures request method, path, response status, duration, IP address, and user agent.
- Tamper-resistant: application code only issues `INSERT` statements against the audit log.
