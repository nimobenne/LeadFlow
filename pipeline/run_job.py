"""
run_job.py — One-shot pipeline runner for GitHub Actions.

Reads job config from environment variables set by the workflow,
runs the full pipeline once, then exits.

Environment variables (set by GitHub Actions workflow):
    PIPELINE_JOB_ID       Supabase job ID created by the dashboard
    PIPELINE_CITIES       Comma-separated city names e.g. "London,Manchester"
    PIPELINE_LEAD_LIMIT   Integer e.g. "100"
    PIPELINE_FORCE_REFRESH "true" or "false"

    SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY  (from repo secrets)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# Ensure pipeline root is importable
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from daemon import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_job")


def main() -> None:
    job_id = os.environ.get("PIPELINE_JOB_ID", "").strip()
    cities_raw = os.environ.get("PIPELINE_CITIES", "").strip()
    lead_limit_raw = os.environ.get("PIPELINE_LEAD_LIMIT", "100").strip()
    force_refresh_raw = os.environ.get("PIPELINE_FORCE_REFRESH", "false").strip().lower()

    if not job_id:
        logger.error("PIPELINE_JOB_ID is required.")
        sys.exit(1)

    if not cities_raw:
        logger.error("PIPELINE_CITIES is required.")
        sys.exit(1)

    cities = [c.strip().title() for c in cities_raw.split(",") if c.strip()]
    lead_limit = int(lead_limit_raw) if lead_limit_raw.isdigit() else 100
    force_refresh = force_refresh_raw == "true"

    job = {
        "id": job_id,
        "cities": cities,
        "lead_limit": lead_limit,
        "force_refresh": force_refresh,
    }

    logger.info(
        "Starting one-shot pipeline: job_id=%s cities=%s limit=%d force_refresh=%s",
        job_id, cities, lead_limit, force_refresh,
    )

    asyncio.run(run_pipeline(job))
    logger.info("Pipeline complete. Exiting.")


if __name__ == "__main__":
    main()
