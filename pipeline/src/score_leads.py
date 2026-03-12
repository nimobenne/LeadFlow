"""
score_leads.py — Compute fit_score, confidence_score, and priority_score for each lead.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chain/franchise indicators in business name
# ---------------------------------------------------------------------------

_CHAIN_KEYWORDS = re.compile(
    r"\b(ltd|limited|plc|group|franchise|franchisee|chain|multiple\s+location|"
    r"great\s+clips|supercuts|fantastic\s+sams|toni\s+&?\s*guy|rush\s+hair|"
    r"headmasters|regis|sports\s+clips|floyd.s)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_lead(lead: dict) -> dict:
    """
    Calculate fit_score, confidence_score, priority_score and pricing_fit.

    Scores are clamped to [0, 100].
    Sets stage="scored".
    Returns updated lead dict.
    """
    fit = _compute_fit_score(lead)
    conf = _compute_confidence_score(lead)

    fit = max(0, min(100, fit))
    conf = max(0, min(100, conf))

    priority = round((fit * 0.65) + (conf * 0.35), 2)

    if fit >= 70:
        pricing_fit = "strong"
    elif fit >= 50:
        pricing_fit = "possible"
    else:
        pricing_fit = "weak"

    lead.update(
        {
            "fit_score": fit,
            "confidence_score": conf,
            "priority_score": priority,
            "pricing_fit": pricing_fit,
            "stage": "scored",
        }
    )

    logger.debug(
        "Scored %s: fit=%d conf=%d priority=%.2f",
        lead.get("business_name"),
        fit,
        conf,
        priority,
    )
    return lead


# ---------------------------------------------------------------------------
# Fit Score
# ---------------------------------------------------------------------------


def _compute_fit_score(lead: dict) -> int:
    score = 0

    website = lead.get("website", "")
    site_error = lead.get("site_error", "")
    has_chat_widget = bool(lead.get("has_chat_widget"))
    booking_url = lead.get("booking_url", "")
    whatsapp_present = bool(lead.get("whatsapp_present"))
    has_contact_form = bool(lead.get("has_contact_form"))
    services_visible = bool(lead.get("services_visible"))
    pricing_visible = bool(lead.get("pricing_visible"))
    mobile_cta = lead.get("mobile_cta_strength", "none")
    language = lead.get("language_detected", "en")
    business_name = lead.get("business_name", "")
    multiple_staff = bool(lead.get("multiple_staff"))
    strong_review_count = bool(lead.get("strong_review_count"))
    pain_points: list[str] = lead.get("pain_points", [])
    emails_found: list[str] = lead.get("emails_found", [])
    phone = lead.get("phone", "")

    is_chain = bool(_CHAIN_KEYWORDS.search(business_name))
    has_real_website = bool(website) and not site_error
    is_abandoned = site_error in ("homepage_failed",) or "broken" in site_error.lower() if site_error else False
    is_low_info = not services_visible and not pricing_visible and not emails_found and not booking_url

    # --- Positive signals ---

    # +20 website exists and is functional
    if has_real_website and not is_abandoned:
        score += 20

    # +15 independent shop (not chain)
    if not is_chain:
        score += 15

    # +10 English-language site
    if language == "en":
        score += 10

    # +10 clear services/pricing/booking intent
    if (services_visible or pricing_visible) and booking_url:
        score += 10
    elif services_visible or pricing_visible:
        score += 5

    # +10 mobile site usable
    if mobile_cta != "none":
        score += 10

    # +10 likely repetitive pre-booking questions (services visible and no chat)
    if services_visible and not has_chat_widget:
        score += 10

    # +15 no live chat / no booking assistant
    if not has_chat_widget:
        score += 15

    # +12 phone or contact-form only (no email and has phone)
    if not emails_found and phone:
        score += 12

    # +12 booking link exists but weak/hidden
    if booking_url and mobile_cta in ("weak", "none"):
        score += 12

    # +10 no FAQ/instant answer path
    if "no_faq" in pain_points:
        score += 10

    # +8 no WhatsApp option
    if not whatsapp_present:
        score += 8

    # +8 no after-hours capture
    if "no_after_hours" in pain_points:
        score += 8

    # +10 premium positioning (pricing visible and price signals > £30)
    if pricing_visible and _detect_premium_pricing(lead.get("pricing_visible", False), lead):
        score += 10

    # +8 multiple staff
    if multiple_staff:
        score += 8

    # +6 visible booking link but no assistant
    if booking_url and not has_chat_widget:
        score += 6

    # +6 strong review count/active
    if strong_review_count:
        score += 6

    # --- Negative signals ---

    # -20 already has strong booking assistant/chat
    if has_chat_widget:
        score -= 20

    # -15 chain/franchise
    if is_chain:
        score -= 15

    # -12 no real website (social-only or missing)
    if not has_real_website:
        score -= 12

    # -10 abandoned/broken site
    if is_abandoned:
        score -= 10

    # -8 very low-information site
    if is_low_info and has_real_website:
        score -= 8

    return score


# ---------------------------------------------------------------------------
# Confidence Score
# ---------------------------------------------------------------------------


def _compute_confidence_score(lead: dict) -> int:
    score = 0

    website = lead.get("website", "")
    decision_maker_name = lead.get("decision_maker_name", "")
    personal_email = lead.get("personal_email", "")
    generic_email = lead.get("generic_email", "")
    email_source_url = lead.get("email_source_url", "")
    phone_on_site = bool(lead.get("phones_found"))
    mx_valid = bool(lead.get("mx_valid"))
    mailbox_status = lead.get("mailbox_status", "unknown")
    catch_all = lead.get("catch_all")
    domain_matches_brand = bool(lead.get("domain_matches_brand"))
    source_type = lead.get("source_type", "yell")
    domain = lead.get("domain", "")

    best_email = lead.get("best_email", "")
    best_email_domain = best_email.split("@")[1].lower() if "@" in best_email else ""

    is_personal_on_domain = bool(personal_email) and (
        personal_email.split("@")[1].lower() == domain if "@" in personal_email else False
    )
    is_generic_on_domain = bool(generic_email) and (
        generic_email.split("@")[1].lower() == domain if "@" in generic_email else False
    )

    # --- Positive signals ---

    # +25 official website found
    if website:
        score += 25

    # +15 named owner/manager found
    if decision_maker_name:
        score += 15

    # +15 personal email on company domain
    if is_personal_on_domain:
        score += 15

    # +10 generic email on company domain
    if is_generic_on_domain:
        score += 10

    # +10 source URL captured
    if email_source_url:
        score += 10

    # +10 phone confirmed on site
    if phone_on_site:
        score += 10

    # +10 MX valid
    if mx_valid:
        score += 10

    # +10 mailbox valid
    if mailbox_status == "valid":
        score += 10

    # +5 domain matches brand exactly
    if domain_matches_brand:
        score += 5

    # --- Negative signals ---

    # -15 generic inbox only (no personal email, has generic)
    if not personal_email and generic_email:
        score -= 15

    # -20 catch_all = True
    if catch_all is True:
        score -= 20

    # -20 mailbox_status = "unknown"
    if mailbox_status == "unknown":
        score -= 20

    # -25 invalid/mismatched domain
    if mailbox_status == "invalid" or not domain_matches_brand:
        # only penalise heavily if we actually have an email to judge
        if best_email:
            score -= 25

    # -15 third-party directory only (source_type != "yell" AND no real website)
    if source_type != "yell" and not website:
        score -= 15

    return score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_premium_pricing(pricing_visible: bool, lead: dict) -> bool:
    """
    Heuristic: consider premium if pricing_visible and the corpus mentions
    amounts >= 30 (£30+ per service is premium for UK barbershop/salon).
    """
    if not pricing_visible:
        return False
    # We don't re-parse HTML here; use a simple signal from pain_points/services
    # A more robust approach would store price data during analysis.
    # As a proxy: if pricing is visible and it's not a low-info site → premium assumed
    return bool(lead.get("services_visible"))
