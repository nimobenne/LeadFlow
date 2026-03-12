"""
daemon.py — Main async daemon loop for the LeadFlow pipeline.

Polls Supabase for pending jobs, processes them end-to-end, and writes
heartbeats every 30 seconds.

Usage:
    python daemon.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from openai import AsyncOpenAI
from playwright.async_api import async_playwright, Browser

# Ensure the pipeline root is on sys.path so relative imports work
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.settings import (
    CONCURRENCY,
    HEARTBEAT_INTERVAL,
    OPENAI_API_KEY,
    DATA_DIR,
)
from db.supabase_client import (
    get_pending_job,
    get_job,
    mark_job_running,
    mark_job_completed,
    mark_job_failed,
    save_lead,
    log_progress,
    update_heartbeat,
    reset_stale_jobs,
)
from src.discover import discover_businesses
from src.analyze_site import analyze_site
from src.extract_contacts import extract_contacts
from src.validate_contacts import validate_contacts
from src.score_leads import score_lead
from src.personalize import personalize_lead
from src.export import export_to_csv, export_to_xlsx

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("daemon")


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Main daemon loop — polls for jobs and dispatches pipeline runs."""
    logger.info("LeadFlow daemon starting up.")
    last_heartbeat = 0.0
    current_job_id: Optional[str] = None

    try:
        while True:
            now = time.monotonic()

            # Heartbeat every HEARTBEAT_INTERVAL seconds
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                update_heartbeat()
                last_heartbeat = now

            # Reset orphaned jobs
            reset_stale_jobs()

            job = get_pending_job()
            if job:
                current_job_id = str(job["id"])
                try:
                    await run_pipeline(job)
                except Exception as exc:
                    logger.exception("Unhandled error in pipeline for job %s", current_job_id)
                    mark_job_failed(current_job_id, str(exc)[:500])
                finally:
                    current_job_id = None
            else:
                logger.debug("No pending jobs. Sleeping 10s.")
                await asyncio.sleep(10)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
        if current_job_id:
            logger.info("Marking job %s as failed due to shutdown.", current_job_id)
            mark_job_failed(current_job_id, "Daemon shut down by operator (KeyboardInterrupt)")
        logger.info("Daemon exiting cleanly.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


async def run_pipeline(job: dict) -> None:
    """
    Full end-to-end pipeline for a single job.

    Steps
    -----
    1. Mark job running
    2. Discover businesses via Yell.com
    3. Process each lead through 5 async workers
    4. Mark job completed/failed based on yield rate
    5. Export results to data/ directory
    """
    job_id = str(job["id"])
    cities: list[str] = job.get("cities") or []
    lead_limit: int = int(job.get("lead_limit") or 50)
    force_refresh: bool = bool(job.get("force_refresh") or False)

    if not cities:
        logger.error("Job %s has no cities configured.", job_id)
        mark_job_failed(job_id, "No cities specified in job config.")
        return

    logger.info(
        "Starting pipeline for job %s | cities=%s | limit=%d | force_refresh=%s",
        job_id,
        cities,
        lead_limit,
        force_refresh,
    )
    mark_job_running(job_id)

    log_progress(
        job_id=job_id,
        message=f"Pipeline started. Cities: {', '.join(cities)}. Lead limit: {lead_limit}.",
        stage="started",
        status="info",
    )

    # ------------------------------------------------------------------
    # Step 1: Discovery
    # ------------------------------------------------------------------
    try:
        raw_leads = await discover_businesses(
            cities=cities,
            lead_limit=lead_limit,
            force_refresh=force_refresh,
            job_id=job_id,
        )
    except Exception as exc:
        logger.exception("Discovery failed for job %s", job_id)
        mark_job_failed(job_id, f"Discovery error: {exc}")
        return

    if not raw_leads:
        mark_job_failed(job_id, "Discovery returned zero leads.")
        return

    log_progress(
        job_id=job_id,
        message=f"Discovery complete: {len(raw_leads)} raw leads queued for analysis.",
        stage="discover",
        status="info",
    )

    # ------------------------------------------------------------------
    # Step 2: Parallel worker processing
    # ------------------------------------------------------------------
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    processed_leads: list[dict] = []

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        try:
            tasks = [
                _process_lead(
                    lead=lead,
                    browser=browser,
                    openai_client=openai_client,
                    semaphore=semaphore,
                    job_id=job_id,
                )
                for lead in raw_leads
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await browser.close()

    for res in results:
        if isinstance(res, Exception):
            logger.error("Worker raised exception: %s", res)
        elif res is not None:
            processed_leads.append(res)

    # ------------------------------------------------------------------
    # Step 3: Save all leads to Supabase
    # ------------------------------------------------------------------
    saved_count = 0
    for lead in processed_leads:
        saved = save_lead(lead)
        if saved:
            saved_count += 1

    # ------------------------------------------------------------------
    # Step 4: Export to disk
    # ------------------------------------------------------------------
    if processed_leads:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(DATA_DIR, f"leads_{job_id}_{ts}.csv")
        xlsx_path = os.path.join(DATA_DIR, f"leads_{job_id}_{ts}.xlsx")
        try:
            export_to_csv(processed_leads, csv_path)
            export_to_xlsx(processed_leads, xlsx_path)
            log_progress(
                job_id=job_id,
                message=f"Exported {len(processed_leads)} leads to {csv_path} and {xlsx_path}.",
                stage="export",
                status="info",
            )
        except Exception as exc:
            logger.error("Export failed for job %s: %s", job_id, exc)

    # ------------------------------------------------------------------
    # Step 5: Determine success / failure
    # ------------------------------------------------------------------
    yield_rate = len(processed_leads) / max(lead_limit, 1)
    summary_msg = (
        f"Pipeline finished. Discovered={len(raw_leads)}, "
        f"Processed={len(processed_leads)}, "
        f"Saved={saved_count}, "
        f"Yield={yield_rate:.1%}."
    )
    logger.info(summary_msg)

    log_progress(
        job_id=job_id,
        message=summary_msg,
        stage="summary",
        status="info",
    )

    if yield_rate >= 0.5:
        mark_job_completed(job_id)
    else:
        mark_job_failed(
            job_id,
            f"Yield {yield_rate:.1%} below 50% threshold. "
            f"Found {len(processed_leads)} of {lead_limit} target leads.",
        )


# ---------------------------------------------------------------------------
# Single lead worker
# ---------------------------------------------------------------------------


async def _process_lead(
    lead: dict,
    browser: Browser,
    openai_client: AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    job_id: str,
) -> Optional[dict]:
    """
    Process a single lead through the full pipeline within the semaphore.
    Errors are caught per stage so one bad lead never kills the whole batch.
    """
    async with semaphore:
        business_name = lead.get("business_name", "unknown")

        # -- Stage: analyze_site -------------------------------------------
        try:
            lead = await analyze_site(lead, browser)
            log_progress(
                job_id=job_id,
                message="Site analyzed.",
                stage="analyze",
                business_name=business_name,
                status="info",
            )
        except Exception as exc:
            logger.error("analyze_site error for %s: %s", business_name, exc)
            log_progress(
                job_id=job_id,
                message=f"Site analysis failed: {exc}",
                stage="analyze",
                business_name=business_name,
                status="error",
            )
            # Continue pipeline with whatever data we have

        # -- Stage: extract_contacts ----------------------------------------
        try:
            lead = extract_contacts(lead)
            log_progress(
                job_id=job_id,
                message="Contacts extracted.",
                stage="extract",
                business_name=business_name,
                status="info",
            )
        except Exception as exc:
            logger.error("extract_contacts error for %s: %s", business_name, exc)
            log_progress(
                job_id=job_id,
                message=f"Contact extraction failed: {exc}",
                stage="extract",
                business_name=business_name,
                status="error",
            )

        # -- Stage: validate_contacts ----------------------------------------
        try:
            lead = await validate_contacts(lead)
            log_progress(
                job_id=job_id,
                message=f"Contacts validated (mx={lead.get('mx_valid')}, "
                        f"status={lead.get('mailbox_status')}).",
                stage="validate",
                business_name=business_name,
                status="info",
            )
        except Exception as exc:
            logger.error("validate_contacts error for %s: %s", business_name, exc)
            log_progress(
                job_id=job_id,
                message=f"Contact validation failed: {exc}",
                stage="validate",
                business_name=business_name,
                status="error",
            )

        # -- Stage: score_lead -----------------------------------------------
        try:
            lead = score_lead(lead)
            log_progress(
                job_id=job_id,
                message=(
                    f"Scored: fit={lead.get('fit_score')}, "
                    f"conf={lead.get('confidence_score')}, "
                    f"priority={lead.get('priority_score')}."
                ),
                stage="score",
                business_name=business_name,
                status="info",
            )
        except Exception as exc:
            logger.error("score_lead error for %s: %s", business_name, exc)
            log_progress(
                job_id=job_id,
                message=f"Scoring failed: {exc}",
                stage="score",
                business_name=business_name,
                status="error",
            )

        # -- Stage: personalize_lead -----------------------------------------
        try:
            lead = await personalize_lead(lead, openai_client)
            log_progress(
                job_id=job_id,
                message=f"Personalized (angle={lead.get('outreach_angle')}).",
                stage="personalize",
                business_name=business_name,
                status="info",
            )
        except Exception as exc:
            logger.error("personalize_lead error for %s: %s", business_name, exc)
            log_progress(
                job_id=job_id,
                message=f"Personalization failed: {exc}",
                stage="personalize",
                business_name=business_name,
                status="error",
            )

        return lead


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
