"""
Create a seed organisation and API key for local development and first-run setup.
Usage: python scripts/seed.py --org-name "Acme Pharma" --backend-provider openai \
         --backend-url https://api.openai.com/v1 --backend-key sk-... --backend-model gpt-4o
"""
import asyncio
import uuid
import argparse
from db.session import get_db_session
from db.models.org import Org
from db.models.api_key import APIKey
from db.models.llm_backend import LLMBackend
from core.security.api_keys import generate_api_key
from core.security.encryption import encrypt

async def seed(org_name: str, provider: str, base_url: str, api_key_val: str, model: str):
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    full_key, key_hash = generate_api_key(org_id)

    async with get_db_session() as db:
        org = Org(id=org_id, name=org_name)
        db.add(org)
        await db.flush()

        api_key = APIKey(
            id=f"key_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            name="Default key",
            key_hash=key_hash,
            scope="research:write,research:read",
        )
        db.add(api_key)
        await db.flush()

        backend = LLMBackend(
            id=f"be_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            name=f"{provider}-default",
            provider=provider,
            base_url=base_url,
            api_key_encrypted=encrypt(api_key_val) if api_key_val else None,
            model=model,
            is_default=True,
        )
        db.add(backend)

    print(f"Org ID:  {org_id}")
    print(f"API Key: {full_key}")
    print("(Save this key — it will not be shown again.)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--backend-provider", default="openai")
    parser.add_argument("--backend-url", default="https://api.openai.com/v1")
    parser.add_argument("--backend-key", default="")
    parser.add_argument("--backend-model", default="gpt-4o")
    args = parser.parse_args()
    asyncio.run(seed(args.org_name, args.backend_provider, args.backend_url, args.backend_key, args.backend_model))
