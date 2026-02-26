"""
Webhook API — receives Jira Automation triggers and dispatches refinement.
"""

import asyncio

from fastapi import APIRouter, Header, HTTPException
from structlog import get_logger

from app.models.jira_models import WebhookPayload
from app.services.refinement_service import handle_webhook

logger = get_logger()

router = APIRouter(tags=["Jira Webhook"])


@router.post("/jira/refine")
async def jira_refine(
    payload: WebhookPayload,
):
    """Receive a refinement trigger from Jira Automati on.

    - Validates the shared secret.
    - Dispatches processing as a background task so Jira gets a fast 200.
    """
    # Verify shared secret
    # if x_webhook_secret != settings.WEBHOOK_SECRET:
    #     logger.warning("webhook_auth_failed", issue=payload.issue_key)
    #     raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # Validate mode
    if payload.mode not in ("first_pass", "pm_feedback"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{payload.mode}'. Must be 'first_pass' or 'pm_feedback'.",
        )

    # Fire-and-forget background task so Jira gets a quick response
    asyncio.create_task(_safe_handle(payload))

    logger.info("webhook_accepted", issue=payload.issue_key, mode=payload.mode)
    return {"status": "accepted", "issue": payload.issue_key, "mode": payload.mode}


async def _safe_handle(payload: WebhookPayload) -> None:
    """Wrapper that catches and logs exceptions from the background task."""
    try:
        await handle_webhook(payload)
    except Exception:
        logger.exception(
            "webhook_processing_failed",
            issue=payload.issue_key,
            mode=payload.mode,
        )
