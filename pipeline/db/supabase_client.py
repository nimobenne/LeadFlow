"""
supabase_client.py — Supabase wrapper for all database operations in the LeadFlow pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase import create_client, Client

from config.settings import (
    SUPABASE_URL,
    SUPABASE_KEY,
    LEAD_STALENESS_DAYS,
    STALE_JOB_THRESHOLD_SECONDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------


def get_pending_job() -> Optional[dict]:
    """Return the oldest pending job record, or None if the queue is empty."""
    try:
        client = get_client()
        result = (
            client.table("jobs")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("get_pending_job failed: %s", exc)
        return None


def get_job(job_id: str) -> Optional[dict]:
    """Fetch the full job record for the given job_id."""
    try:
        client = get_client()
        result = (
            client.table("jobs")
            .select("*")
            .eq("id", job_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.error("get_job(%s) failed: %s", job_id, exc)
        return None


def mark_job_running(job_id: str) -> None:
    """Set status=running and record started_at timestamp."""
    try:
        client = get_client()
        client.table("jobs").update(
            {
                "status": "running",
                "started_at": _now_iso(),
            }
        ).eq("id", job_id).execute()
        logger.info("Job %s marked as running.", job_id)
    except Exception as exc:
        logger.error("mark_job_running(%s) failed: %s", job_id, exc)


def mark_job_completed(job_id: str) -> None:
    """Set status=completed and record completed_at timestamp."""
    try:
        client = get_client()
        client.table("jobs").update(
            {
                "status": "completed",
                "completed_at": _now_iso(),
            }
        ).eq("id", job_id).execute()
        logger.info("Job %s marked as completed.", job_id)
    except Exception as exc:
        logger.error("mark_job_completed(%s) failed: %s", job_id, exc)


def mark_job_failed(job_id: str, reason: str) -> None:
    """Set status=failed, record completed_at, and log to progress_events."""
    try:
        client = get_client()
        client.table("jobs").update(
            {
                "status": "failed",
                "completed_at": _now_iso(),
            }
        ).eq("id", job_id).execute()
        logger.warning("Job %s marked as failed: %s", job_id, reason)
        log_progress(
            job_id=job_id,
            message=f"Job failed: {reason}",
            stage="failed",
            status="error",
        )
    except Exception as exc:
        logger.error("mark_job_failed(%s) failed: %s", job_id, exc)


def reset_stale_jobs() -> None:
    """
    Any job with status=running and started_at older than STALE_JOB_THRESHOLD_SECONDS
    is considered orphaned — reset it to pending so it can be retried.
    """
    try:
        client = get_client()
        cutoff = datetime.now(tz=timezone.utc) - timedelta(
            seconds=STALE_JOB_THRESHOLD_SECONDS
        )
        result = (
            client.table("jobs")
            .update({"status": "pending"})
            .eq("status", "running")
            .lt("started_at", cutoff.isoformat())
            .execute()
        )
        rows = result.data or []
        if rows:
            logger.info("Reset %d stale job(s) to pending.", len(rows))
    except Exception as exc:
        logger.error("reset_stale_jobs failed: %s", exc)


# ---------------------------------------------------------------------------
# Lead persistence
# ---------------------------------------------------------------------------


def save_lead(lead_dict: dict) -> Optional[dict]:
    """
    Upsert a lead into the `leads` table.
    Deduplication key: (domain, city) — updates the existing row if matched.
    Returns the saved row dict or None on error.
    """
    try:
        client = get_client()
        # Ensure timestamps are set
        now = _now_iso()
        lead_dict.setdefault("created_at", now)
        lead_dict["updated_at"] = now

        result = (
            client.table("leads")
            .upsert(
                lead_dict,
                on_conflict="domain,city",
                returning="representation",
            )
            .execute()
        )
        rows = result.data or []
        saved = rows[0] if rows else None
        if saved:
            logger.debug(
                "Saved lead: %s (%s)", lead_dict.get("business_name"), lead_dict.get("domain")
            )
        return saved
    except Exception as exc:
        logger.error(
            "save_lead failed for %s: %s", lead_dict.get("business_name"), exc
        )
        return None


def lead_exists(domain: str, phone: str) -> bool:
    """
    Return True if a lead with this domain OR phone was created within the
    last LEAD_STALENESS_DAYS days (i.e. it is fresh enough to skip).
    """
    try:
        client = get_client()
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(days=LEAD_STALENESS_DAYS)
        ).isoformat()

        filters: list[dict] = []
        if domain:
            filters.append({"domain": domain})
        if phone:
            filters.append({"phone": phone})

        if not filters:
            return False

        # Build OR filter string for supabase-py
        or_parts: list[str] = []
        if domain:
            or_parts.append(f"domain.eq.{domain}")
        if phone:
            or_parts.append(f"phone.eq.{phone}")

        result = (
            client.table("leads")
            .select("id,created_at")
            .or_(",".join(or_parts))
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return len(rows) > 0
    except Exception as exc:
        logger.error("lead_exists check failed: %s", exc)
        # On error, be permissive and allow the lead through
        return False


# ---------------------------------------------------------------------------
# Progress events
# ---------------------------------------------------------------------------


def log_progress(
    job_id: str,
    message: str,
    stage: str = "general",
    business_name: Optional[str] = None,
    status: str = "info",
) -> None:
    """Insert a progress event row for real-time dashboard updates."""
    try:
        client = get_client()
        row: dict[str, Any] = {
            "job_id": job_id,
            "message": message,
            "stage": stage,
            "status": status,
            "created_at": _now_iso(),
        }
        if business_name:
            row["business_name"] = business_name
        client.table("progress_events").insert(row).execute()
        logger.info("[%s] %s — %s", stage.upper(), business_name or "", message)
    except Exception as exc:
        # Never let logging failures crash the pipeline
        logger.error("log_progress failed: %s", exc)


# ---------------------------------------------------------------------------
# Daemon heartbeat
# ---------------------------------------------------------------------------


def update_heartbeat() -> None:
    """Upsert a single daemon_status row (id=1) with the current timestamp."""
    try:
        client = get_client()
        client.table("daemon_status").upsert(
            {"id": 1, "last_seen_at": _now_iso()},
            on_conflict="id",
        ).execute()
    except Exception as exc:
        logger.error("update_heartbeat failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
