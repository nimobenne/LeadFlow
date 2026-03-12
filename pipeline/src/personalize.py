"""
personalize.py — Generate personalised outreach copy for each lead via OpenAI GPT-4o-mini.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a B2B sales copywriter for WidgetAI — an AI chat widget product designed for \
UK hair salons and barbershops. Your job is to analyse a specific business's website \
signals and produce personalised, concise outreach copy.

Respond ONLY with a valid JSON object containing exactly these three fields:
- "personalization_note": 1-2 sentence specific observation about their website or setup \
  (mention concrete details like their booking platform, phone-only contact, lack of chat, etc.)
- "likely_missed_lead_issue": 1 sentence describing the core revenue/lead problem WidgetAI would solve
- "outreach_angle": one of exactly these values — \
  "missed_bookings_after_hours", "too_much_manual_replying", \
  "website_traffic_not_converting", "repetitive_questions", \
  "visitors_leaving_before_booking"

Be specific and genuine. Avoid generic filler. Reference the actual signals provided.\
"""

_USER_TEMPLATE = """\
Business: {business_name}
City: {city}
Has live chat widget: {has_chat_widget}
Has contact form: {has_contact_form}
Booking URL found: {booking_url}
Booking platform: {booking_platform}
WhatsApp present: {whatsapp_present}
Book-now button above fold: {book_now_above_fold}
Services visible on site: {services_visible}
Pricing visible on site: {pricing_visible}
Decision maker name: {decision_maker_name}
Detected pain points: {pain_points}
Mobile CTA strength: {mobile_cta_strength}
Multiple staff on team page: {multiple_staff}
Fit score: {fit_score}
Confidence score: {confidence_score}

Based on the above signals, produce the JSON output.\
"""

# Valid outreach angles
_VALID_ANGLES = {
    "missed_bookings_after_hours",
    "too_much_manual_replying",
    "website_traffic_not_converting",
    "repetitive_questions",
    "visitors_leaving_before_booking",
}

# Fallback values used when the API call fails
_FALLBACK_NOTE = (
    "Their website appears to rely on a phone number for customer contact, which means "
    "visitors arriving outside business hours may leave without booking."
)
_FALLBACK_ISSUE = (
    "Without an automated chat assistant, potential customers with quick questions may "
    "abandon the site instead of converting into bookings."
)
_FALLBACK_ANGLE = "missed_bookings_after_hours"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def personalize_lead(lead: dict, openai_client: AsyncOpenAI) -> dict:
    """
    Call OpenAI GPT-4o-mini to generate personalised outreach fields.

    Adds:
      - personalization_note
      - likely_missed_lead_issue
      - outreach_angle

    Sets stage="personalized".
    Returns updated lead dict.
    """
    prompt = _build_prompt(lead)

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=400,
            timeout=30,
        )
        raw_json = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse error for personalization of %s: %s",
            lead.get("business_name"),
            exc,
        )
        parsed = {}
    except Exception as exc:
        logger.error(
            "OpenAI call failed for %s: %s",
            lead.get("business_name"),
            exc,
        )
        parsed = {}

    # Validate and extract fields with fallbacks
    personalization_note = _extract_str(parsed, "personalization_note", _FALLBACK_NOTE)
    likely_missed_lead_issue = _extract_str(
        parsed, "likely_missed_lead_issue", _FALLBACK_ISSUE
    )
    outreach_angle = _extract_angle(parsed, _FALLBACK_ANGLE)

    lead.update(
        {
            "personalization_note": personalization_note,
            "likely_missed_lead_issue": likely_missed_lead_issue,
            "outreach_angle": outreach_angle,
            "stage": "personalized",
        }
    )

    logger.debug(
        "Personalized %s: angle=%s", lead.get("business_name"), outreach_angle
    )
    return lead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_prompt(lead: dict) -> str:
    pain_points = lead.get("pain_points", [])
    if isinstance(pain_points, list):
        pain_str = ", ".join(pain_points) if pain_points else "none detected"
    else:
        pain_str = str(pain_points)

    return _USER_TEMPLATE.format(
        business_name=lead.get("business_name", "Unknown"),
        city=lead.get("city", "Unknown"),
        has_chat_widget=_yn(lead.get("has_chat_widget")),
        has_contact_form=_yn(lead.get("has_contact_form")),
        booking_url=lead.get("booking_url") or "not found",
        booking_platform=lead.get("booking_platform") or "none",
        whatsapp_present=_yn(lead.get("whatsapp_present")),
        book_now_above_fold=_yn(lead.get("book_now_above_fold")),
        services_visible=_yn(lead.get("services_visible")),
        pricing_visible=_yn(lead.get("pricing_visible")),
        decision_maker_name=lead.get("decision_maker_name") or "not found",
        pain_points=pain_str,
        mobile_cta_strength=lead.get("mobile_cta_strength", "none"),
        multiple_staff=_yn(lead.get("multiple_staff")),
        fit_score=lead.get("fit_score", 0),
        confidence_score=lead.get("confidence_score", 0),
    )


def _yn(value: Any) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def _extract_str(data: dict, key: str, fallback: str) -> str:
    val = data.get(key)
    if isinstance(val, str) and val.strip():
        return val.strip()
    return fallback


def _extract_angle(data: dict, fallback: str) -> str:
    val = data.get("outreach_angle", "")
    if isinstance(val, str) and val.strip() in _VALID_ANGLES:
        return val.strip()
    return fallback
