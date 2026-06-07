"""
Smoke test against a live running stack.
Set E2E_API_KEY and E2E_BASE_URL environment variables before running.
"""
import os
import asyncio
import httpx
import pytest
import time

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("E2E_API_KEY", "")

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_ready():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_submit_and_poll_job():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    query = "What are the main competitive players in the CAR-T cell therapy market?"

    async with httpx.AsyncClient() as client:
        # Submit
        r = await client.post(
            f"{BASE_URL}/v1/research",
            json={"query": query, "max_rounds": 1},
            headers=headers,
        )
    assert r.status_code == 202
    job_id = r.json()["id"]

    # Poll until complete or timeout (5 minutes)
    deadline = time.time() + 300
    final_status = None
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            r = await client.get(f"{BASE_URL}/v1/research/{job_id}", headers=headers)
            assert r.status_code == 200
            status = r.json()["status"]
            if status in ("completed", "failed", "cancelled"):
                final_status = status
                break
            await asyncio.sleep(5)

    assert final_status == "completed", f"Job ended with status: {final_status}"
    data = r.json()
    assert "report" in data
    assert len(data["report"]["body_md"]) > 100
