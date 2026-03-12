"""
extract_contacts.py — Normalise and rank contact information from an analyzed lead.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generic/role-based email local parts
# ---------------------------------------------------------------------------

GENERIC_LOCAL_PARTS = {
    "info", "hello", "hi", "hey", "contact", "bookings", "booking",
    "enquiries", "enquiry", "enquire", "reception", "admin", "support",
    "help", "team", "office", "mail", "email", "salon", "shop", "studio",
    "barber", "barbershop", "hair", "appointments", "appointment",
}


def extract_contacts(lead: dict) -> dict:
    """
    Rank and assign contact fields from the analyzed lead dict.

    Modifies and returns the lead dict with stage="contacts_extracted".
    """
    website: str = lead.get("website", "")
    emails_found: list[str] = lead.get("emails_found", [])
    email_source_urls: dict[str, str] = lead.get("email_source_urls", {})
    decision_maker_name: str = lead.get("decision_maker_name", "")

    # -- Domain ----------------------------------------------------------------
    domain = _extract_root_domain(website)
    lead["domain"] = domain

    # -- Classify emails -------------------------------------------------------
    personal_email: Optional[str] = None
    generic_email: Optional[str] = None

    domain_emails = [e for e in emails_found if _email_domain(e) == domain]
    external_emails = [e for e in emails_found if _email_domain(e) != domain]

    # 1. Personal email on company domain: local part contains the
    #    decision_maker_name tokens OR does NOT match a generic local part
    if domain_emails:
        personal_candidates = _filter_personal(domain_emails, decision_maker_name)
        if personal_candidates:
            personal_email = personal_candidates[0]

        generic_candidates = _filter_generic(domain_emails)
        if generic_candidates:
            generic_email = generic_candidates[0]

        # If no clear personal found but there are non-generic domain emails, treat first as personal
        if not personal_email and domain_emails:
            non_generic = [e for e in domain_emails if e not in (generic_candidates or [])]
            if non_generic:
                personal_email = non_generic[0]

    # 2. If no domain email at all, fall back to any found email
    if not personal_email and not generic_email:
        if emails_found:
            # Classify the first available email
            first = emails_found[0]
            if _is_generic_local(first):
                generic_email = first
            else:
                personal_email = first

    # -- Best email for outreach -----------------------------------------------
    # Priority: personal on domain > generic on domain > any personal > any generic
    best_email = personal_email or generic_email or (emails_found[0] if emails_found else None)

    # -- Email source URL -------------------------------------------------------
    email_source_url = ""
    if best_email:
        email_source_url = email_source_urls.get(best_email, website)

    # -- Source type -----------------------------------------------------------
    lead["source_type"] = lead.get("source_type", "yell")

    lead.update(
        {
            "domain": domain,
            "personal_email": personal_email or "",
            "generic_email": generic_email or "",
            "best_email": best_email or "",
            "email_source_url": email_source_url,
            "stage": "contacts_extracted",
        }
    )

    logger.debug(
        "Contacts extracted for %s: personal=%s generic=%s best=%s",
        lead.get("business_name"),
        personal_email,
        generic_email,
        best_email,
    )
    return lead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_root_domain(url: str) -> str:
    """Return root domain (no scheme, no www, no path)."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        return netloc.lstrip("www.")
    except Exception:
        return ""


def _email_domain(email: str) -> str:
    """Return the domain portion of an email address."""
    parts = email.split("@")
    if len(parts) == 2:
        return parts[1].lower()
    return ""


def _local_part(email: str) -> str:
    """Return the local part of an email address."""
    return email.split("@")[0].lower() if "@" in email else email.lower()


def _is_generic_local(email: str) -> bool:
    return _local_part(email) in GENERIC_LOCAL_PARTS


def _filter_personal(emails: list[str], decision_maker_name: str) -> list[str]:
    """
    Return emails whose local part suggests a personal name.
    Priority: contains decision_maker_name tokens > not in generic list.
    """
    dm_tokens = set(
        t.lower() for t in re.split(r"\W+", decision_maker_name) if t
    ) if decision_maker_name else set()

    named: list[str] = []
    non_generic: list[str] = []

    for email in emails:
        local = _local_part(email)
        if dm_tokens and any(t in local for t in dm_tokens):
            named.append(email)
        elif not _is_generic_local(email):
            non_generic.append(email)

    return named or non_generic


def _filter_generic(emails: list[str]) -> list[str]:
    """Return emails whose local part is in the generic set."""
    return [e for e in emails if _is_generic_local(e)]
