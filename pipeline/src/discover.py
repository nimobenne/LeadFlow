"""
discover.py — Scrape FreeIndex.co.uk to discover barbershop/hair salon listings for given UK cities.

Uses category URLs with Load More clicking:
  /categories/health_and_beauty/hair_care/barbers/(london)/
  /categories/health_and_beauty/hair_care/hairdressers/(london)/
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
    FREEINDEX_CATEGORIES,
    FREEINDEX_MAX_LOAD_MORE,
)
from db.supabase_client import lead_exists, log_progress

logger = logging.getLogger(__name__)

FREEINDEX_BASE = "https://www.freeindex.co.uk"

# Profile links follow /profile(name)_ID.htm — used to identify listing containers
PROFILE_LINK_SELECTOR = "a[href*='/profile(']"

# Load More button
LOAD_MORE_SELECTORS = [
    "button[onclick*='LoadMore']",
    "a[onclick*='LoadMore']",
    "button:has-text('Show More')",
    "a:has-text('Show More')",
    "button:has-text('Load More')",
    "[class*='load-more']",
    "[class*='loadmore']",
]

_BLOCK_INDICATORS = [
    "text=Access Denied",
    "#challenge-form",
    "iframe[src*='captcha']",
    "text=unusual traffic",
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
    """Scrape FreeIndex category pages for barbershops/hair salons across UK cities."""
    leads: list[dict] = []
    num_cities = max(len(cities), 1)
    num_cats = len(FREEINDEX_CATEGORIES)
    per_cat_quota = max(1, lead_limit // num_cities // num_cats)

    log_progress(
        job_id=job_id,
        message=(
            f"Starting discovery across {num_cities} cities, "
            f"quota {per_cat_quota} per category, force_refresh={force_refresh}"
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
            ],
        )
        try:
            for city in cities:
                city_leads: list[dict] = []
                for cat_url_template in FREEINDEX_CATEGORIES:
                    cat_leads = await _scrape_category(
                        browser=browser,
                        url=cat_url_template.format(city=city.lower().replace(" ", "-")),
                        city=city,
                        quota=per_cat_quota,
                        force_refresh=force_refresh,
                        job_id=job_id,
                    )
                    city_leads.extend(cat_leads)
                    log_progress(
                        job_id=job_id,
                        message=f"Found {len(cat_leads)} results in {city} ({cat_url_template.split('/')[7]}).",
                        stage="discover",
                        status="info",
                    )
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                # Deduplicate within city
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


async def _scrape_category(
    browser: Browser,
    url: str,
    city: str,
    quota: int,
    force_refresh: bool,
    job_id: str,
) -> list[dict]:
    """Load a FreeIndex category+city page, click Load More up to N times, extract listings."""
    ua = random.choice(USER_AGENTS)
    context: BrowserContext = await browser.new_context(
        user_agent=ua,
        locale="en-GB",
        timezone_id="Europe/London",
        viewport={"width": 1280, "height": 900},
    )
    results: list[dict] = []

    try:
        page: Page = await context.new_page()

        try:
            await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="load")
        except PlaywrightTimeout:
            logger.warning("Timeout loading FreeIndex page: %s", url)
            await page.close()
            return []

        if await _is_blocked(page):
            logger.warning("Block detected on %s", url)
            await _save_debug(page, city, "blocked")
            await page.close()
            return []

        # Wait for profile links to appear
        try:
            await page.wait_for_selector(PROFILE_LINK_SELECTOR, timeout=10000)
        except PlaywrightTimeout:
            logger.warning("No profile links found on %s — saving debug.", url)
            await _save_debug(page, city, url.split("/")[7] if "/" in url else "cat")
            await page.close()
            return []

        # Click Load More up to FREEINDEX_MAX_LOAD_MORE times to get more results
        for i in range(FREEINDEX_MAX_LOAD_MORE):
            current_count = len(await page.query_selector_all(PROFILE_LINK_SELECTOR))
            if current_count >= quota:
                break

            clicked = await _click_load_more(page)
            if not clicked:
                break

            # Wait for new listings to appear
            await asyncio.sleep(random.uniform(1.5, 2.5))
            new_count = len(await page.query_selector_all(PROFILE_LINK_SELECTOR))
            logger.debug("Load More %d: %d → %d profile links", i + 1, current_count, new_count)
            if new_count == current_count:
                break  # No new results loaded

        # Extract all visible listings
        results = await _parse_listings(page, city, quota, force_refresh)
        await page.close()

    finally:
        await context.close()

    return results


async def _click_load_more(page: Page) -> bool:
    """Try to click the Load More / Show More button. Returns True if clicked."""
    for sel in LOAD_MORE_SELECTORS:
        try:
            btn = await page.query_selector(sel)
            if btn:
                is_visible = await btn.is_visible()
                if is_visible:
                    await btn.click()
                    return True
        except Exception:
            continue
    return False


async def _parse_listings(
    page: Page,
    city: str,
    quota: int,
    force_refresh: bool,
) -> list[dict]:
    """Extract lead dicts from all profile links on the page."""
    leads: list[dict] = []

    # Get all profile links — each is a business listing
    profile_links = await page.query_selector_all(PROFILE_LINK_SELECTOR)
    logger.debug("Parsing %d profile links on page.", len(profile_links))

    seen_names: set[str] = set()

    for link in profile_links:
        if len(leads) >= quota:
            break
        try:
            lead = await _extract_from_profile_link(link, page, city)
        except Exception as exc:
            logger.debug("Extraction error: %s", exc)
            continue

        if not lead or not lead.get("business_name"):
            continue

        # Skip duplicates within this page
        name_key = lead["business_name"].lower().strip()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        # Dedup against Supabase
        if not force_refresh and lead_exists(
            domain=lead.get("domain", ""),
            phone=lead.get("phone", ""),
        ):
            logger.debug("Skipping known lead: %s", lead["business_name"])
            continue

        leads.append(lead)

    return leads


async def _extract_from_profile_link(link, page: Page, city: str) -> Optional[dict]:
    """Extract business details from a profile link and its surrounding context."""
    # Business name from link text
    business_name = (await link.inner_text()).strip()
    if not business_name or len(business_name) < 2:
        return None

    # Profile URL
    href = await link.get_attribute("href") or ""
    freeindex_url = urljoin(FREEINDEX_BASE, href) if href else ""

    # Try to find the parent container for this listing
    # Walk up to find a container with more details
    container = None
    for _ in range(5):
        try:
            parent = await link.evaluate_handle("el => el.parentElement")
            parent_html = await parent.evaluate("el => el.innerHTML")
            # Look for a container that has location/phone info
            if any(x in parent_html for x in ["_place_", "phone", "tel:", "address", "review"]):
                container = parent
                break
            link = parent
        except Exception:
            break

    # Extract text content from container for parsing
    container_text = ""
    if container:
        try:
            container_text = await container.evaluate("el => el.innerText")
        except Exception:
            pass

    # Extract phone from container text or tel: links
    phone = ""
    try:
        if container:
            tel_link = await container.query_selector("a[href^='tel:']")
            if tel_link:
                phone = (await tel_link.get_attribute("href") or "").replace("tel:", "").strip()
    except Exception:
        pass

    # Extract website from container
    website = ""
    try:
        if container:
            for link_el in await container.query_selector_all("a[href^='http']"):
                href_val = await link_el.get_attribute("href") or ""
                if "freeindex.co.uk" not in href_val and href_val.startswith("http"):
                    website = href_val.strip()
                    break
    except Exception:
        pass

    # Extract address — look for location text after map pin icon
    address = ""
    if container_text:
        # FreeIndex uses "_place_" as a text marker for location
        lines = [l.strip() for l in container_text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "_place_" in line or "place" in line.lower():
                if i + 1 < len(lines):
                    address = lines[i + 1]
                    break

    domain = _extract_root_domain(website) if website else ""

    return {
        "business_name": business_name,
        "address": address or city,
        "city": city,
        "phone": _normalise_phone(phone),
        "website": website,
        "domain": domain,
        "yell_listing_url": freeindex_url,
        "source_type": "freeindex",
        "stage": "discovered",
    }


async def _is_blocked(page: Page) -> bool:
    try:
        title = await page.title()
        if "access denied" in title.lower() or "captcha" in title.lower():
            return True
    except Exception:
        pass
    for sel in _BLOCK_INDICATORS:
        try:
            if await page.query_selector(sel):
                return True
        except Exception:
            pass
    return False


async def _save_debug(page: Page, city: str, label: str) -> None:
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        slug = f"{city}_{label}".replace(" ", "_").lower()
        html_path = os.path.join(data_dir, f"debug_{slug}.html")
        png_path = os.path.join(data_dir, f"debug_{slug}.png")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(await page.content())
        await page.screenshot(path=png_path, full_page=False)
        logger.info("Debug saved: %s", html_path)
    except Exception as exc:
        logger.debug("Debug save failed: %s", exc)


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
