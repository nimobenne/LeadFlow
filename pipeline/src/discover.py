"""
discover.py — Scrape Yell.com to discover barbershop/hair salon listings for given UK cities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Optional
from urllib.parse import urlencode, urljoin

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from config.settings import (
    PLAYWRIGHT_TIMEOUT_MS,
    USER_AGENTS,
    YELL_KEYWORDS,
    YELL_MAX_PAGES,
    YELL_SEARCH_URL,
)
from db.supabase_client import lead_exists, log_progress

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YELL_BASE = "https://www.yell.com"

# Selectors — these may need updating if Yell changes their DOM
LISTING_SELECTOR = "article.businessCapsule--mainRow, div[class*='businessCapsule'], li[class*='listing']"
NAME_SELECTORS = [
    "h2[class*='businessCapsule--title'] a",
    "h2[class*='businessName'] a",
    "a[class*='businessCapsule--title']",
    ".business-name a",
]
ADDRESS_SELECTORS = [
    "span[class*='businessCapsule--address']",
    "address",
    "[class*='address']",
]
PHONE_SELECTORS = [
    "span[class*='businessCapsule--telephone']",
    "a[href^='tel:']",
    "[class*='phone']",
    "[class*='telephone']",
]
WEBSITE_SELECTORS = [
    "a[data-ya-track='website']",
    "a[class*='businessCapsule--website']",
    "a[href*='http'][class*='website']",
]
LISTING_URL_SELECTORS = [
    "h2[class*='businessCapsule--title'] a",
    "a[class*='businessCapsule--title']",
    "h2[class*='businessName'] a",
]

# Backoff delays on block detection (seconds)
_BACKOFF_DELAYS = [30, 120]

# Selectors that indicate Yell served a block/CAPTCHA page
_BLOCK_INDICATORS = [
    "text=Access Denied",
    "text=Please verify you are a human",
    "text=unusual traffic",
    "#challenge-form",
    "iframe[src*='captcha']",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def discover_businesses(
    cities: list[str],
    lead_limit: int,
    force_refresh: bool,
    job_id: str,
) -> list[dict]:
    """
    Scrape Yell.com for barbershop/hair salon listings across all cities.

    Parameters
    ----------
    cities        : list of UK city/town names
    lead_limit    : total target number of leads across all cities
    force_refresh : if True, skip the dedup check
    job_id        : Supabase job ID for progress logging

    Returns
    -------
    List of lead dicts (stage="discovered")
    """
    leads: list[dict] = []

    # Distribute budget: per-city, per-keyword quota
    num_cities = max(len(cities), 1)
    num_keywords = len(YELL_KEYWORDS)
    per_search_quota = max(
        1,
        (lead_limit // num_cities // num_keywords),
    )

    log_progress(
        job_id=job_id,
        message=(
            f"Starting discovery across {num_cities} cities, "
            f"quota {per_search_quota} per search, "
            f"force_refresh={force_refresh}"
        ),
        stage="discover",
        status="info",
    )

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ],
        )

        try:
            for city in cities:
                city_leads: list[dict] = []
                for keyword in YELL_KEYWORDS:
                    kw_leads = await _scrape_keyword(
                        browser=browser,
                        keyword=keyword,
                        city=city,
                        quota=per_search_quota,
                        force_refresh=force_refresh,
                        job_id=job_id,
                    )
                    city_leads.extend(kw_leads)

                    log_progress(
                        job_id=job_id,
                        message=(
                            f"Found {len(kw_leads)} results for '{keyword}' in {city}."
                        ),
                        stage="discover",
                        status="info",
                    )

                    # Brief pause between keyword searches for the same city
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                # Deduplicate within city by business_name+address
                seen = set()
                for lead in city_leads:
                    key = _dedup_key(lead)
                    if key not in seen:
                        seen.add(key)
                        leads.append(lead)

        finally:
            await browser.close()

    log_progress(
        job_id=job_id,
        message=f"Discovery complete — {len(leads)} unique businesses found.",
        stage="discover",
        status="info",
    )
    return leads


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _scrape_keyword(
    browser: Browser,
    keyword: str,
    city: str,
    quota: int,
    force_refresh: bool,
    job_id: str,
) -> list[dict]:
    """Scrape a single keyword+city combination across up to YELL_MAX_PAGES pages."""
    ua = random.choice(USER_AGENTS)
    context: BrowserContext = await browser.new_context(
        user_agent=ua,
        locale="en-GB",
        timezone_id="Europe/London",
        viewport={"width": 1280, "height": 900},
    )
    results: list[dict] = []
    backoff_index = 0

    try:
        for page_num in range(1, YELL_MAX_PAGES + 1):
            if len(results) >= quota:
                break

            url = _build_url(keyword, city, page_num)
            page: Page = await context.new_page()

            try:
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
            except PlaywrightTimeout:
                logger.warning("Timeout loading Yell page: %s", url)
                await page.close()
                break

            # --- Block detection ---
            blocked = await _is_blocked(page)
            if blocked:
                logger.warning(
                    "Yell block detected on page %d for '%s' in %s. "
                    "Backoff index: %d",
                    page_num,
                    keyword,
                    city,
                    backoff_index,
                )
                await page.close()
                if backoff_index < len(_BACKOFF_DELAYS):
                    delay = _BACKOFF_DELAYS[backoff_index]
                    backoff_index += 1
                    logger.info("Waiting %ds before retrying...", delay)
                    await asyncio.sleep(delay)
                    # Retry same page with fresh context
                    await context.close()
                    ua = random.choice(USER_AGENTS)
                    context = await browser.new_context(
                        user_agent=ua,
                        locale="en-GB",
                        timezone_id="Europe/London",
                        viewport={"width": 1280, "height": 900},
                    )
                    continue
                else:
                    logger.error(
                        "Giving up on '%s' in %s after repeated blocks.", keyword, city
                    )
                    break

            # --- Parse listings ---
            page_leads = await _parse_listings(page, city, force_refresh)

            # Debug: dump HTML and screenshot when no results found on page 1
            if page_num == 1 and not page_leads:
                try:
                    html = await page.content()
                    debug_html_path = os.path.join(
                        os.path.dirname(__file__), "..", "data", f"debug_{city}_{keyword}.html"
                    )
                    os.makedirs(os.path.dirname(debug_html_path), exist_ok=True)
                    with open(debug_html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    logger.info("Debug HTML saved to %s", debug_html_path)
                    await page.screenshot(
                        path=debug_html_path.replace(".html", ".png"), full_page=False
                    )
                    logger.info("Debug screenshot saved.")
                except Exception as dbg_exc:
                    logger.debug("Debug dump failed: %s", dbg_exc)

            await page.close()

            for lead in page_leads:
                if len(results) >= quota:
                    break
                results.append(lead)
                logger.debug("Discovered: %s (%s)", lead.get("business_name"), city)

            if not page_leads:
                # No listings means we've hit the last page
                break

            # Random delay between pages
            await asyncio.sleep(random.uniform(1.0, 2.5))

    finally:
        await context.close()

    return results


async def _parse_listings(page: Page, city: str, force_refresh: bool) -> list[dict]:
    """Extract lead dicts from all listing cards on the current Yell results page."""
    leads: list[dict] = []

    # Wait for listings to appear (short timeout — if not there, just return empty)
    try:
        await page.wait_for_selector(LISTING_SELECTOR, timeout=8000)
    except PlaywrightTimeout:
        logger.debug("No listing elements found on page.")
        return []

    listing_elements = await page.query_selector_all(LISTING_SELECTOR)

    for el in listing_elements:
        try:
            lead = await _extract_listing(el, city)
        except Exception as exc:
            logger.debug("Failed to extract listing: %s", exc)
            continue

        if not lead:
            continue

        # Skip entries without a website — we can't do anything useful with them
        if not lead.get("website"):
            continue

        # Dedup check (skip if we've seen this domain/phone recently)
        if not force_refresh and lead_exists(
            domain=lead.get("domain", ""),
            phone=lead.get("phone", ""),
        ):
            logger.debug(
                "Skipping duplicate: %s", lead.get("business_name")
            )
            continue

        leads.append(lead)

    return leads


async def _extract_listing(el, city: str) -> Optional[dict]:
    """Extract fields from a single listing element."""
    # Business name
    business_name = ""
    for sel in NAME_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            business_name = (await node.inner_text()).strip()
            if business_name:
                break

    if not business_name:
        return None

    # Address
    address = ""
    for sel in ADDRESS_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            address = (await node.inner_text()).strip()
            if address:
                break

    # Phone
    phone = ""
    for sel in PHONE_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            raw = await node.get_attribute("href") or await node.inner_text()
            phone = raw.replace("tel:", "").strip()
            if phone:
                break

    # Website URL
    website = ""
    for sel in WEBSITE_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            href = await node.get_attribute("href") or ""
            if href.startswith("http") and "yell.com" not in href:
                website = href.strip()
                break

    # Yell listing URL
    yell_listing_url = ""
    for sel in LISTING_URL_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            href = await node.get_attribute("href") or ""
            if href:
                yell_listing_url = (
                    href if href.startswith("http") else urljoin(YELL_BASE, href)
                )
                break

    domain = _extract_root_domain(website) if website else ""

    return {
        "business_name": business_name,
        "address": address,
        "city": city,
        "phone": _normalise_phone(phone),
        "website": website,
        "domain": domain,
        "yell_listing_url": yell_listing_url,
        "source_type": "yell",
        "stage": "discovered",
    }


def _build_url(keyword: str, city: str, page: int) -> str:
    """Build a Yell search URL for the given keyword, city, and page number."""
    base = YELL_SEARCH_URL.format(
        keyword=keyword.replace(" ", "+"),
        city=city.replace(" ", "+"),
    )
    if page > 1:
        base = f"{base}&pageNum={page}"
    return base


async def _is_blocked(page: Page) -> bool:
    """Return True if Yell returned a block/challenge page."""
    try:
        title = await page.title()
        if "access denied" in title.lower() or "captcha" in title.lower():
            return True
    except Exception:
        pass

    for selector in _BLOCK_INDICATORS:
        try:
            el = await page.query_selector(selector)
            if el:
                return True
        except Exception:
            pass
    return False


def _extract_root_domain(url: str) -> str:
    """Return the root domain (no www) from a URL."""
    if not url:
        return ""
    match = re.search(r"https?://(?:www\.)?([^/?\s]+)", url)
    if match:
        return match.group(1).lower()
    return ""


def _normalise_phone(phone: str) -> str:
    """Strip all non-digit characters except leading +."""
    if not phone:
        return ""
    phone = phone.strip()
    # Keep leading + for international
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)


def _dedup_key(lead: dict) -> str:
    name = (lead.get("business_name") or "").lower().strip()
    address = (lead.get("address") or "").lower().strip()[:30]
    return f"{name}|{address}"
