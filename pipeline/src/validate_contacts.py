"""
validate_contacts.py — DNS/MX validation and inbox classification for lead emails.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

import dns.resolver
import dns.exception

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMAIL_SYNTAX_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

ROLE_BASED_LOCAL_PARTS = {
    "info", "admin", "contact", "hello", "bookings", "enquiries",
    "reception", "support", "noreply", "no-reply", "webmaster",
    "postmaster", "abuse", "mailer-daemon", "sales", "marketing",
    "press", "team", "office",
}

# DNS resolver timeout (seconds)
DNS_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def validate_contacts(lead: dict) -> dict:
    """
    Validate the best available email in the lead dict using DNS/MX checks.

    Adds the following fields:
      - mx_valid (bool)
      - mailbox_status ("valid" | "invalid" | "unknown")
      - catch_all (bool | None)
      - role_based (bool)
      - domain_matches_brand (bool)
      - last_verified_at (ISO datetime str)

    Sets stage="validated".
    """
    email = lead.get("best_email") or lead.get("personal_email") or lead.get("generic_email") or ""

    if not email:
        lead.update(
            {
                "mx_valid": False,
                "mailbox_status": "unknown",
                "catch_all": None,
                "role_based": False,
                "domain_matches_brand": False,
                "last_verified_at": _now_iso(),
                "stage": "validated",
            }
        )
        return lead

    local, domain = _split_email(email)

    # Run DNS checks in thread pool to avoid blocking the event loop
    mx_valid, a_record_exists = await asyncio.get_event_loop().run_in_executor(
        None, _check_dns, domain
    )

    syntax_valid = bool(EMAIL_SYNTAX_RE.match(email))
    role_based = local in ROLE_BASED_LOCAL_PARTS

    if not syntax_valid or not a_record_exists:
        mailbox_status = "invalid"
    elif mx_valid:
        mailbox_status = "valid"
    else:
        mailbox_status = "unknown"

    # Catch-all: heuristic — we can't verify without SMTP, mark as unknown
    catch_all: Optional[bool] = None  # True/False/None

    domain_matches_brand = _domain_matches_brand(domain, lead.get("business_name", ""))

    lead.update(
        {
            "mx_valid": mx_valid,
            "mailbox_status": mailbox_status,
            "catch_all": catch_all,
            "role_based": role_based,
            "domain_matches_brand": domain_matches_brand,
            "last_verified_at": _now_iso(),
            "stage": "validated",
        }
    )

    logger.debug(
        "Validated %s: mx=%s status=%s role_based=%s brand_match=%s",
        email,
        mx_valid,
        mailbox_status,
        role_based,
        domain_matches_brand,
    )
    return lead


# ---------------------------------------------------------------------------
# DNS helpers (blocking — run in executor)
# ---------------------------------------------------------------------------


def _check_dns(domain: str) -> tuple[bool, bool]:
    """
    Returns (mx_valid, a_record_exists).
    Both checks are done with dnspython.
    """
    resolver = dns.resolver.Resolver()
    resolver.lifetime = DNS_TIMEOUT
    resolver.timeout = DNS_TIMEOUT

    a_exists = _has_a_record(resolver, domain)
    mx_exists = _has_mx_record(resolver, domain)

    return mx_exists, a_exists


def _has_a_record(resolver: dns.resolver.Resolver, domain: str) -> bool:
    """Return True if the domain has at least one A or AAAA record."""
    for rtype in ("A", "AAAA"):
        try:
            resolver.resolve(domain, rtype)
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            continue
        except Exception:
            continue
    return False


def _has_mx_record(resolver: dns.resolver.Resolver, domain: str) -> bool:
    """Return True if the domain has at least one MX record."""
    try:
        answers = resolver.resolve(domain, "MX")
        return len(answers) > 0
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        return False
    except dns.exception.Timeout:
        logger.debug("DNS timeout for MX lookup of %s", domain)
        return False
    except Exception as exc:
        logger.debug("MX lookup error for %s: %s", domain, exc)
        return False


# ---------------------------------------------------------------------------
# Brand matching
# ---------------------------------------------------------------------------


def _domain_matches_brand(domain: str, business_name: str) -> bool:
    """
    Fuzzy-match: normalise both domain and business_name, then check overlap.
    E.g. domain "johnsbarbershop.co.uk" vs name "John's Barbershop" → True
    """
    if not domain or not business_name:
        return False

    norm_domain = _normalise(domain.split(".")[0])
    norm_name = _normalise(business_name)

    # Remove common suffixes/stopwords
    stopwords = {"barbershop", "barbers", "barber", "salon", "hair", "the",
                 "and", "ltd", "limited", "co", "uk", "shop", "studio"}
    name_tokens = {t for t in norm_name.split() if t not in stopwords}
    domain_tokens = {t for t in norm_domain.split() if t not in stopwords}

    if not name_tokens or not domain_tokens:
        return False

    # Jaccard similarity
    intersection = name_tokens & domain_tokens
    union = name_tokens | domain_tokens
    score = len(intersection) / len(union)

    return score >= 0.3


def _normalise(text: str) -> str:
    """Lowercase, strip accents, remove non-alphanumeric."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_email(email: str) -> tuple[str, str]:
    parts = email.rsplit("@", 1)
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower()
    return email.lower(), ""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
