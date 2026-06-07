import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from db.session import get_db_session
from db.models.report import Report

router = APIRouter(prefix="/v1", tags=["reports"])


@router.get("/reports/{report_id}/export")
async def export_report(report_id: str, format: str = "md", request: Request = None):
    org_id = request.state.org_id

    async with get_db_session() as db:
        report = await db.get(Report, report_id)

    if not report or report.org_id != org_id:
        raise HTTPException(status_code=404, detail="Report not found")

    if format == "md":
        return PlainTextResponse(
            content=report.content_md or "",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="report-{report_id}.md"'},
        )
    elif format == "json":
        citations = json.loads(report.content_json).get("citations", []) if report.content_json else []
        return JSONResponse({
            "id": report.id,
            "summary": report.summary,
            "body_md": report.content_md,
            "citations": citations,
        })
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported: md, json")
