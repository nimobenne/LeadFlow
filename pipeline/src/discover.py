"""
discover.py — Scrape FreeIndex.co.uk to discover barbershop/hair salon listings for given UK cities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Optional
from urllib.parse import urljoin

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
    FREEINDEX_KEYWORDS,
    FREEINDEX_MAX_PAGES,
    FREEINDEX_SEARCH_URL,
)
from db.supabase_client import lead_exists, log_progress

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FREEINDEX_BASE = "https://www.freeindex.co.uk"

# Listing container — FreeIndex wraps each result in a ranked-list item
LISTING_SELECTOR = (
    "div.ranked-list__item, "
    "li.search-result, "
    "div[class*='ranked'], "
    "div[class*='result-item'], "
    "article[class*='result']"
)

# Business name selectors (fallback chain)
NAME_SELECTORS = [
    "h2.ranked-list__company-name a",
    "h2[class*='company-name'] a",
    "h3[class*='company-name'] a",
    "a[class*='company-name']",
    "h2 a",
    "h3 a",
]

# Address selectors
ADDRESS_SELECTORS = [
    "span[class*='address']",
    "p[class*='address']",
    "div[class*='address']",
    "address",
    "[itemprop='address']",
]

# Phone selectors
PHONE_SELECTORS = [
    "a[href^='tel:']",
    "span[class*='phone']",
    "span[class*='telephone']",
    "[itemprop='telephone']",
    "[class*='phone-number']",
]

# Website link selectors
WEBSITE_SELECTORS = [
    "a[class*='website']",
    "a[data-track*='website']",
    "a[rel='nofollow noopener'][target='_blank']:not([href*='freeindex'])",
]

# Listing page URL selectors
LISTING_URL_SELECTORS = [
    "h2.ranked-list__company-name a",
    "h2[class*='company-name'] a",
    "h3[class*='company-name'] a",
    "a[class*='company-name']",
    "h2 a",
]

# Pagination — FreeIndex uses ?page=N
_BACKOFF_DELAYS = [30, 120]

_BLOCK_INDICATORS = [
    "text=Access Denied",
    "text=Please verify you are a human",
    "text=unusual traffic",
    "#challenge-form",
    "iframe[src*='captcha']",
    "text=Enable JavaScript",
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
    Scrape FreeIndex.co.uk for barbershop/hair salon listings across all cities.
    """
    leads: list[dict] = []

    num_cities = max(len(cities), 1)
    num_keywords = len(FREEINDEX_KEYWORDS)
    per_search_quota = max(1, (lead_limit // num_cities // num_keywords))

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
                for keyword in FREEINDEX_KEYWORDS:
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
                        message=f"Found {len(kw_leads)} results for '{keyword}' in {city}.",
                        stage="discover",
                        status="info",
                    )

                    await asyncio.sleep(random.uniform(1.5, 3.0))

                # Deduplicate within city by business_name+address
                seen: set[str] = set()
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
    """Scrape a single keyword+city combination across up to FREEINDEX_MAX_PAGES pages."""
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
        for page_num in range(1, FREEINDEX_MAX_PAGES + 1):
            if len(results) >= quota:
                break

            url = _build_url(keyword, city, page_num)
            page: Page = await context.new_page()

            try:
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="load")
            except PlaywrightTimeout:
                logger.warning("Timeout loading FreeIndex page: %s", url)
                await page.close()
                break

            # Block detection
            blocked = await _is_blocked(page)
            if blocked:
                logger.warning(
                    "Block detected on page %d for '%s' in %s. Backoff index: %d",
                    page_num, keyword, city, backoff_index,
                )
                await page.close()
                if backoff_index < len(_BACKOFF_DELAYS):
                    delay = _BACKOFF_DELAYS[backoff_index]
                    backoff_index += 1
                    logger.info("Waiting %ds before retrying...", delay)
                    await asyncio.sleep(delay)
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
                    logger.error("Giving up on '%s' in %s after repeated blocks.", keyword, city)
                    break

            # Parse listings
            page_leads = await _parse_listings(page, city, force_refresh)

            # Debug: save HTML + screenshot when page 1 returns nothing
            if page_num == 1 and not page_leads:
                await _save_debug(page, city, keyword)

            await page.close()

            for lead in page_leads:
                if len(results) >= quota:
                    break
                results.append(lead)
                logger.debug("Discovered: %s (%s)", lead.get("business_name"), city)

            if not page_leads:
                break

            await asyncio.sleep(random.uniform(1.0, 2.5))

    finally:
        await context.close()

    return results


async def _parse_listings(page: Page, city: str, force_refresh: bool) -> list[dict]:
    """Extract lead dicts from all listing cards on the current FreeIndex results page."""
    leads: list[dict] = []

    try:
        await page.wait_for_selector(LISTING_SELECTOR, timeout=8000)
    except PlaywrightTimeout:
        logger.debug("No listing elements found on page (selector timeout).")
        return []

    listing_elements = await page.query_selector_all(LISTING_SELECTOR)
    logger.debug("Found %d raw listing elements.", len(listing_elements))

    for el in listing_elements:
        try:
            lead = await _extract_listing(el, page, city)
        except Exception as exc:
            logger.debug("Failed to extract listing: %s", exc)
            continue

        if not lead:
            continue

        # Skip entries without a website
        if not lead.get("website"):
            continue

        # Dedup check
        if not force_refresh and lead_exists(
            domain=lead.get("domain", ""),
            phone=lead.get("phone", ""),
        ):
            logger.debug("Skipping duplicate: %s", lead.get("business_name"))
            continue

        leads.append(lead)

    return leads


async def _extract_listing(el, page: Page, city: str) -> Optional[dict]:
    """Extract fields from a single FreeIndex listing element."""
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

    # Website URL — FreeIndex wraps external links through a redirect
    website = ""
    for sel in WEBSITE_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            href = await node.get_attribute("href") or ""
            if href and "freeindex.co.uk" not in href and href.startswith("http"):
                website = href.strip()
                break

    # FreeIndex listing URL
    freeindex_listing_url = ""
    for sel in LISTING_URL_SELECTORS:
        node = await el.query_selector(sel)
        if node:
            href = await node.get_attribute("href") or ""
            if href:
                freeindex_listing_url = (
                    href if href.startswith("http") else urljoin(FREEINDEX_BASE, href)
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
        "yell_listing_url": freeindex_listing_url,  # reusing field for source listing URL
        "source_type": "freeindex",
        "stage": "discovered",
    }


def _build_url(keyword: str, city: str, page: int) -> str:
    """Build a FreeIndex search URL."""
    url = FREEINDEX_SEARCH_URL.format(
        keyword=keyword.replace(" ", "+"),
        city=city.replace(" ", "+"),
    )
    if page > 1:
        url = f"{url}&page={page}"
    return url


async def _is_blocked(page: Page) -> bool:
    """Return True if the page is a block/challenge page."""
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


async def _save_debug(page: Page, city: str, keyword: str) -> None:
    """Save HTML and screenshot for debugging when no results are found."""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        slug = f"{city}_{keyword}".replace(" ", "_").lower()
        html_path = os.path.join(data_dir, f"debug_{slug}.html")
        png_path = os.path.join(data_dir, f"debug_{slug}.png")
        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        await page.screenshot(path=png_path, full_page=False)
        logger.info("Debug files saved: %s, %s", html_path, png_path)
    except Exception as exc:
        logger.debug("Debug dump failed: %s", exc)


def _extract_root_domain(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"https?://(?:www\.)?([^/?\s]+)", url)
    return match.group(1).lower() if match else ""


def _normalise_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)


def _dedup_key(lead: dict) -> str:
    name = (lead.get("business_name") or "").lower().strip()
    address = (lead.get("address") or "").lower().strip()[:30]
    return f"{name}|{address}"
