import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from db.session import get_db_session
from db.models.webhook import WebhookEndpoint

router = APIRouter(prefix="/v1", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    secret: str


class WebhookResponse(BaseModel):
    id: str
    url: str
    is_active: bool


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(body: WebhookCreate, request: Request):
    webhook_id = f"wh_{uuid.uuid4().hex[:12]}"

    from core.security.encryption import encrypt
    async with get_db_session() as db:
        webhook = WebhookEndpoint(
            id=webhook_id,
            url=body.url,
            secret=encrypt(body.secret),
            is_active=True
        )
        db.add(webhook)

    return WebhookResponse(id=webhook_id, url=body.url, is_active=True)


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(request: Request):
    async with get_db_session() as db:
        stmt = select(WebhookEndpoint)
        result = await db.execute(stmt)
        endpoints = result.scalars().all()

    return [WebhookResponse(id=ep.id, url=ep.url, is_active=ep.is_active) for ep in endpoints]


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str, request: Request):
    async with get_db_session() as db:
        webhook = await db.get(WebhookEndpoint, webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        await db.delete(webhook)
