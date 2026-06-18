from sqlalchemy import select
from db.session import get_db_session
from db.models.claim import Claim
from core.llm.client import LLMClient

class MemoryStore:
    def __init__(self, job_id: str, llm: LLMClient):
        self.job_id = job_id
        self.llm = llm

    async def search_memory(self, topic: str, limit: int = 5) -> list[dict]:
        if not self.job_id:
            return []
            
        # 1. Embed the topic
        try:
            emb = await self.llm.embed(topic)
            if not emb:
                return []
        except Exception:
            return []
            
        # 2. Search Postgres using pgvector
        async with get_db_session() as db:
            stmt = select(Claim).where(Claim.job_id == self.job_id).order_by(Claim.embedding.cosine_distance(emb)).limit(limit)
            results = await db.execute(stmt)
            claims = results.scalars().all()
            return [{"id": c.id, "fact": c.fact} for c in claims]

    async def search_global_memory(self, topic: str, limit: int = 10) -> list[dict]:
        try:
            emb = await self.llm.embed(topic)
            if not emb:
                return []
        except Exception:
            return []
            
        async with get_db_session() as db:
            stmt = select(Claim).order_by(Claim.embedding.cosine_distance(emb)).limit(limit)
            results = await db.execute(stmt)
            claims = results.scalars().all()
            return [{
                "id": c.id, 
                "job_id": c.job_id,
                "source_id": c.source_id,
                "fact": c.fact,
                "trust_score": getattr(c, "trust_score", None)
            } for c in claims]
