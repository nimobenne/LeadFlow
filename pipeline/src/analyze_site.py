"""
analyze_site.py — Visit a business website with Playwright and extract all contact/signal data.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
)

from config.settings import PLAYWRIGHT_TIMEOUT_MS, USER_AGENTS
import random

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Booking platform detection patterns
# ---------------------------------------------------------------------------

BOOKING_PLATFORMS: list[tuple[str, str]] = [
    (r"fresha\.com", "fresha"),
    (r"treatwell\.co\.uk|treatwell\.com", "treatwell"),
    (r"booksy\.com", "booksy"),
    (r"squareup\.com|square\.site|squarespace\.com/appointments", "square"),
    (r"vagaro\.com", "vagaro"),
    (r"acuityscheduling\.com", "acuity"),
    (r"calendly\.com", "calendly"),
    (r"timely\.is", "timely"),
    (r"setmore\.com", "setmore"),
    (r"simplybook\.me", "simplybook"),
    (r"glofox\.com", "glofox"),
    (r"mindbodyonline\.com|mindbody\.io", "mindbody"),
]

# Chat widget detection (script src or element patterns)
CHAT_WIDGETS: list[tuple[str, str]] = [
    (r"intercom\.io|intercom\.com", "intercom"),
    (r"tidio\.co|tidiochat\.com", "tidio"),
    (r"drift\.com", "drift"),
    (r"zopim\.com|zendesk\.com/chat", "zendesk"),
    (r"livechatinc\.com|livechat\.com", "livechat"),
    (r"tawk\.to", "tawk"),
    (r"crisp\.chat", "crisp"),
    (r"freshchat", "freshchat"),
    (r"hubspot\.com/conversations", "hubspot_chat"),
    (r"smartsupp\.com", "smartsupp"),
    (r"olark\.com", "olark"),
    (r"purechat\.com", "purechat"),
    (r"chaport\.com", "chaport"),
]

# Sub-pages to visit (relative paths to check)
SUB_PAGE_PATHS = ["/contact", "/about", "/booking", "/book", "/appointments",
                  "/team", "/our-team", "/about-us", "/contact-us"]

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)
PHONE_RE = re.compile(
    r"(?:\+44|0)[\s\-.]?(?:\d[\s\-.]?){9,10}",
)
PRICE_RE = re.compile(r"£\s*\d+")
OWNER_ROLES = ["owner", "founder", "director", "proprietor", "manager"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_site(lead: dict, browser: Browser) -> dict:
    """
    Visit the business website, extract signals and contact info.

    Parameters
    ----------
    lead    : lead dict containing at minimum 'website'
    browser : shared Playwright browser instance

    Returns
    -------
    Updated lead dict with stage="analyzed"
    """
    website = lead.get("website", "")
    if not website:
        lead["stage"] = "analyzed"
        lead["site_error"] = "no_website"
        return lead

    ua = random.choice(USER_AGENTS)
    context: BrowserContext = await browser.new_context(
        user_agent=ua,
        locale="en-GB",
        timezone_id="Europe/London",
        viewport={"width": 1280, "height": 900},
        ignore_https_errors=True,
    )

    try:
        result = await _analyze_with_context(lead, context, website)
    except Exception as exc:
        logger.error("analyze_site failed for %s: %s", website, exc)
        lead["stage"] = "analyzed"
        lead["site_error"] = str(exc)[:200]
        result = lead
    finally:
        await context.close()

    return result


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------


async def _analyze_with_context(
    lead: dict, context: BrowserContext, website: str
) -> dict:
    """Full analysis within a browser context."""
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_links: list[str] = []
    html_corpus: str = ""
    booking_url: Optional[str] = None
    booking_platform: str = "none"
    whatsapp_present: bool = False
    has_contact_form: bool = False
    has_chat_widget: bool = False
    chat_widget_name: str = ""
    book_now_above_fold: bool = False
    services_visible: bool = False
    pricing_visible: bool = False
    decision_maker_name: str = ""
    decision_maker_role: str = ""
    visited_urls: set[str] = set()
    email_source_url: dict[str, str] = {}  # email -> url where it was found
    language_detected: str = "en"

    # Step 1: Load homepage
    homepage_html, homepage_text, homepage_links = await _load_page(
        context, website, visited_urls
    )
    if homepage_html is None:
        lead.update(
            {
                "stage": "analyzed",
                "site_error": "homepage_failed",
                "has_chat_widget": False,
                "has_contact_form": False,
                "whatsapp_present": False,
            }
        )
        return lead

    html_corpus += homepage_html
    all_links.extend(homepage_links)

    # Extract from homepage immediately
    emails_home = EMAIL_RE.findall(homepage_html)
    for e in emails_home:
        if e not in all_emails:
            all_emails.append(e)
            email_source_url[e] = website

    phones_home = PHONE_RE.findall(homepage_text)
    all_phones.extend(phones_home)

    # Check above-the-fold CTA on homepage
    book_now_above_fold = await _check_book_now_above_fold(context, website)

    # Detect chat widget on homepage (scripts are usually in <head>)
    _widget_found, _widget_name = _detect_chat_widget(homepage_html)
    if _widget_found:
        has_chat_widget = True
        chat_widget_name = _widget_name

    # Step 2: Find and visit up to 4 relevant sub-pages
    subpages_to_visit = _select_subpages(homepage_links, website, SUB_PAGE_PATHS)
    subpages_to_visit = subpages_to_visit[:4]

    for sub_url in subpages_to_visit:
        sub_html, sub_text, sub_links = await _load_page(context, sub_url, visited_urls)
        if sub_html is None:
            continue

        html_corpus += sub_html
        all_links.extend(sub_links)

        sub_emails = EMAIL_RE.findall(sub_html)
        for e in sub_emails:
            if e not in all_emails:
                all_emails.append(e)
                email_source_url[e] = sub_url

        sub_phones = PHONE_RE.findall(sub_text)
        all_phones.extend(sub_phones)

        # Decision maker extraction (About/Team pages are best)
        if any(kw in sub_url.lower() for kw in ["/about", "/team"]):
            dm_name, dm_role = _extract_decision_maker(sub_html)
            if dm_name and not decision_maker_name:
                decision_maker_name = dm_name
                decision_maker_role = dm_role

        if not has_chat_widget:
            _wf, _wn = _detect_chat_widget(sub_html)
            if _wf:
                has_chat_widget = True
                chat_widget_name = _wn

    # Step 3: Aggregate signals from full corpus
    services_visible = _detect_services(html_corpus)
    pricing_visible = bool(PRICE_RE.search(html_corpus))
    has_contact_form = _detect_contact_form(html_corpus)
    whatsapp_present = _detect_whatsapp(html_corpus, all_links)

    booking_url, booking_platform = _detect_booking(html_corpus, all_links)

    # Decision maker from homepage if not found in subpages
    if not decision_maker_name:
        dm_name, dm_role = _extract_decision_maker(homepage_html)
        decision_maker_name = dm_name
        decision_maker_role = dm_role

    # Mobile CTA strength
    mobile_cta_strength = _assess_mobile_cta(book_now_above_fold, booking_url, html_corpus)

    # Language detection (simple heuristic)
    language_detected = _detect_language(homepage_html)

    # Deduplicate phones
    seen_phones: set[str] = set()
    unique_phones = []
    for p in all_phones:
        normalised = re.sub(r"\s+", "", p)
        if normalised not in seen_phones:
            seen_phones.add(normalised)
            unique_phones.append(normalised)

    # Pain point detection
    pain_points = _detect_pain_points(
        has_chat_widget=has_chat_widget,
        has_contact_form=has_contact_form,
        booking_url=booking_url,
        whatsapp_present=whatsapp_present,
        all_emails=all_emails,
        html_corpus=html_corpus,
    )

    # Multiple staff detection
    multiple_staff = _detect_multiple_staff(html_corpus)

    # Active/review count signal from Yell listing URL (basic)
    strong_review_count = _detect_review_signals(lead.get("yell_listing_url", ""), html_corpus)

    lead.update(
        {
            "emails_found": all_emails,
            "email_source_urls": email_source_url,
            "phones_found": unique_phones,
            # best phone: prefer one that's on the site
            "phone": lead.get("phone") or (unique_phones[0] if unique_phones else ""),
            "booking_url": booking_url or "",
            "booking_platform": booking_platform,
            "whatsapp_present": whatsapp_present,
            "has_contact_form": has_contact_form,
            "has_chat_widget": has_chat_widget,
            "chat_widget_name": chat_widget_name,
            "book_now_above_fold": book_now_above_fold,
            "mobile_cta_strength": mobile_cta_strength,
            "services_visible": services_visible,
            "pricing_visible": pricing_visible,
            "language_detected": language_detected,
            "decision_maker_name": decision_maker_name,
            "decision_maker_role": decision_maker_role,
            "pain_points": pain_points,
            "multiple_staff": multiple_staff,
            "strong_review_count": strong_review_count,
            "stage": "analyzed",
        }
    )
    return lead


async def _load_page(
    context: BrowserContext,
    url: str,
    visited: set[str],
) -> tuple[Optional[str], Optional[str], list[str]]:
    """
    Load a page and return (html, text, links).
    Returns (None, None, []) on failure.
    """
    if url in visited:
        return None, None, []
    visited.add(url)

    page: Optional[Page] = None
    try:
        page = await context.new_page()
        await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
        html = await page.content()
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        links = await _collect_links(page, url)
        return html, text, links
    except PlaywrightTimeout:
        logger.debug("Timeout on %s", url)
        return None, None, []
    except Exception as exc:
        logger.debug("Failed to load %s: %s", url, exc)
        return None, None, []
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


async def _collect_links(page: Page, base_url: str) -> list[str]:
    """Collect all href links from the page."""
    try:
        hrefs = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href)",
        )
        return [str(h) for h in hrefs if h]
    except Exception:
        return []


async def _check_book_now_above_fold(context: BrowserContext, url: str) -> bool:
    """Check if a booking/CTA button is visible in the first viewport."""
    page: Optional[Page] = None
    try:
        page = await context.new_page()
        await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
        cta_patterns = [
            "text=Book Now", "text=Book Online", "text=Book Appointment",
            "text=Book", "text=Reserve", "text=Schedule",
            "[class*='book-now']", "[class*='cta']", "[id*='book']",
        ]
        for pattern in cta_patterns:
            try:
                el = await page.query_selector(pattern)
                if el:
                    box = await el.bounding_box()
                    if box and box["y"] < 900:  # within first viewport
                        return True
            except Exception:
                continue
        return False
    except Exception:
        return False
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass


def _select_subpages(links: list[str], base_url: str, target_paths: list[str]) -> list[str]:
    """
    From the link list, select URLs that match target sub-page paths.
    Prioritise: contact > about > booking > book > team.
    """
    base_domain = _root_domain(base_url)
    result: list[str] = []
    seen: set[str] = set()

    for path in target_paths:
        for link in links:
            if _root_domain(link) != base_domain:
                continue
            parsed = urlparse(link)
            if path.rstrip("/") in parsed.path.lower() and link not in seen:
                seen.add(link)
                result.append(link)
                break  # one match per path pattern

    return result


def _detect_chat_widget(html: str) -> tuple[bool, str]:
    """Return (True, widget_name) if a chat widget script/element is detected."""
    html_lower = html.lower()
    for pattern, name in CHAT_WIDGETS:
        if re.search(pattern, html_lower):
            return True, name
    # Generic fallback: look for common chat widget class names
    generic_patterns = [
        r'class=["\'][^"\']*\bchat\b[^"\']*["\']',
        r'id=["\'][^"\']*\bchat\b[^"\']*["\']',
        r'<script[^>]*chat[^>]*>',
    ]
    for pat in generic_patterns:
        if re.search(pat, html_lower):
            return True, "generic_chat"
    return False, ""


def _detect_booking(html: str, links: list[str]) -> tuple[Optional[str], str]:
    """Return (booking_url, platform_name) or (None, 'none')."""
    # Check links first (most reliable)
    for link in links:
        for pattern, name in BOOKING_PLATFORMS:
            if re.search(pattern, link, re.IGNORECASE):
                return link, name

    # Check html src/href attributes
    for pattern, name in BOOKING_PLATFORMS:
        if re.search(pattern, html, re.IGNORECASE):
            # Try to extract the actual URL
            m = re.search(
                rf'https?://[^\s"\'<>]*{pattern}[^\s"\'<>]*',
                html,
                re.IGNORECASE,
            )
            url = m.group(0) if m else None
            return url, name

    # Generic booking/appointment link
    for link in links:
        if re.search(r"/(book|booking|appointment|reserve|schedule)", link, re.IGNORECASE):
            return link, "generic_link"

    return None, "none"


def _detect_contact_form(html: str) -> bool:
    """Detect presence of a contact form (form with email/name fields)."""
    forms = re.findall(r"<form[^>]*>(.*?)</form>", html, re.IGNORECASE | re.DOTALL)
    for form in forms:
        has_email_field = bool(re.search(r'type=["\']email["\']|name=["\'][^"\']*email', form, re.IGNORECASE))
        has_name_field = bool(re.search(r'type=["\']text["\']|name=["\'][^"\']*name', form, re.IGNORECASE))
        has_textarea = bool(re.search(r"<textarea", form, re.IGNORECASE))
        if (has_email_field or has_name_field) and has_textarea:
            return True
        if has_email_field and has_name_field:
            return True
    return False


def _detect_whatsapp(html: str, links: list[str]) -> bool:
    """Check for WhatsApp links or references."""
    for link in links:
        if "wa.me" in link or "whatsapp.com" in link or "api.whatsapp" in link:
            return True
    return bool(re.search(r"whatsapp", html, re.IGNORECASE))


def _detect_services(html: str) -> bool:
    """Detect if services/treatments are listed on the page."""
    service_keywords = [
        "haircut", "trim", "fade", "colour", "color", "highlights",
        "balayage", "blowout", "blow dry", "styling", "perm", "treatment",
        "beard", "shave", "wax", "keratin", "extensions",
    ]
    html_lower = html.lower()
    hits = sum(1 for kw in service_keywords if kw in html_lower)
    return hits >= 3


def _extract_decision_maker(html: str) -> tuple[str, str]:
    """
    Look for owner/founder/director names in bio sections.
    Returns (name, role) or ("", "").
    """
    # Pattern: "Role Name" or "Name, Role" near role keywords
    for role in OWNER_ROLES:
        # "<Role>: Name" or "Name is the <role>"
        patterns = [
            rf"\b{role}\b[,:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
            rf"([A-Z][a-z]+ [A-Z][a-z]+)[,\s]+(?:is\s+(?:the\s+)?)?{role}",
            rf"<(?:h[1-6]|strong|b)[^>]*>[^<]*{role}[^<]*</(?:h[1-6]|strong|b)>",
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                # Grab the first named group or any captured name
                name = ""
                for group in m.groups():
                    if group and re.match(r"[A-Z][a-z]+ [A-Z][a-z]+", group):
                        name = group.strip()
                        break
                if name:
                    return name, role

    return "", ""


def _detect_pain_points(
    has_chat_widget: bool,
    has_contact_form: bool,
    booking_url: Optional[str],
    whatsapp_present: bool,
    all_emails: list[str],
    html_corpus: str,
) -> list[str]:
    """Build list of detected pain point identifiers."""
    points: list[str] = []

    if not has_chat_widget:
        points.append("no_chat")

    has_email = len(all_emails) > 0
    has_phone = bool(re.search(PHONE_RE, html_corpus))

    if has_phone and not has_email and not has_chat_widget:
        points.append("phone_only")

    if not booking_url:
        points.append("no_booking")

    if not has_chat_widget and not re.search(r"faq", html_corpus, re.IGNORECASE):
        points.append("no_faq")

    # No mobile CTA is handled by mobile_cta_strength="none" in calling code
    if not whatsapp_present:
        points.append("no_whatsapp")

    # After-hours: no chatbot, no WhatsApp, no 24h booking
    if not has_chat_widget and not whatsapp_present:
        points.append("no_after_hours")

    return points


def _assess_mobile_cta(
    book_now_above_fold: bool,
    booking_url: Optional[str],
    html_corpus: str,
) -> str:
    if book_now_above_fold:
        return "strong"
    if booking_url or re.search(r"book\s+(now|online|appointment)", html_corpus, re.IGNORECASE):
        return "weak"
    return "none"


def _detect_language(html: str) -> str:
    """Simple language detection from <html lang> attribute or default to 'en'."""
    m = re.search(r'<html[^>]+lang=["\']([a-z]{2})', html, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return "en"


def _detect_multiple_staff(html: str) -> bool:
    """Check for team/staff/stylists sections suggesting multiple employees."""
    patterns = [
        r"our\s+team", r"meet\s+the\s+team", r"our\s+stylists",
        r"our\s+barbers", r"our\s+staff", r"the\s+team",
        r"\d+\s+(?:stylists?|barbers?|staff)",
    ]
    for pat in patterns:
        if re.search(pat, html, re.IGNORECASE):
            return True
    return False


def _detect_review_signals(yell_url: str, html_corpus: str) -> bool:
    """Detect if the listing has strong review count/activity."""
    # Basic signal: review mentions
    return bool(re.search(r"\b\d{2,}\s*(?:reviews?|ratings?)\b", html_corpus, re.IGNORECASE))


def _root_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return ""
