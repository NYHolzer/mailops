from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .config import MatchCriteria, PrintRule


@dataclass(frozen=True)
class InferenceResult:
    rule: PrintRule
    confidence: str  # "high" | "medium" | "low"
    explanation: str


def _lower_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k.lower(): v for k, v in headers.items()}


def infer_print_rule(rule_name: str, example_headers: list[dict[str, str]]) -> InferenceResult:
    """
    Infer a durable newsletter match criteria from one or more example emails.

    Priority:
      1) List-Id contains (very stable) -> high confidence
      2) From domain + List-Unsubscribe present -> medium confidence
      3) From exact -> low confidence
    """
    if not example_headers:
        raise ValueError("No example headers provided for inference.")

    lowered = [_lower_headers(h) for h in example_headers]

    list_ids = [h.get("list-id", "") for h in lowered if h.get("list-id")]
    unsub = any("list-unsubscribe" in h for h in lowered)

    from_vals = [h.get("from", "") for h in lowered if h.get("from")]

    # Heuristic: If List-Id exists, use a substring that is likely stable.
    if list_ids:
        # Use the first List-Id and take the domain-ish chunk if available.
        # Example: "<daily.join1440.com>" or "<something.list-id.vendor>"
        li = list_ids[0].strip()
        # Strip angle brackets if present
        li_clean = li.strip("<>").strip()
        # For matching, we store a "contains" token that’s likely stable:
        token = li_clean
        # If it looks like it has spaces, take first segment
        token = token.split()[0]
        # If it is very long, keep last 60 chars (stable suffix tends to include domain)
        if len(token) > 80:
            token = token[-60:]

        rule = PrintRule(
            name=rule_name,
            action="print",
            match=MatchCriteria(
                header_list_id_contains=token,
                requires_unsubscribe_header=unsub,
            ),
        )
        return InferenceResult(
            rule=rule,
            confidence="high",
            explanation=f"Using List-Id header contains '{token}'."
            + (" Also requiring List-Unsubscribe header." if unsub else ""),
        )

    # Fallback: derive from-domain (best effort)
    # We do not parse fully here; we keep it simple and match by from_exact later if needed.
    if from_vals:
        # Attempt domain extraction from something like "Name <addr@domain>"
        from email.utils import parseaddr

        domains: list[str] = []
        addrs: list[str] = []
        for fv in from_vals:
            _, addr = parseaddr(fv)
            # If parseaddr returns a non-email but we had one, or if it mangles a simple string
            if "@" not in addr and "@" not in fv:
                 # It's just a name, use the whole thing
                 addr = fv
            addr = addr or fv
            addrs.append(addr.strip())
            if "@" in addr:
                domains.append(addr.split("@", 1)[1].lower())

        if domains:
            dom = domains[0]
            rule = PrintRule(
                name=rule_name,
                action="print",
                match=MatchCriteria(
                    from_domain=dom,
                    requires_unsubscribe_header=unsub,
                ),
            )
            return InferenceResult(
                rule=rule,
                confidence="medium",
                explanation=f"Using From domain '{dom}'"
                + (" and requiring List-Unsubscribe header." if unsub else "."),
            )

        # Last fallback: from exact
        addr0 = addrs[0]
        rule = PrintRule(
            name=rule_name,
            action="print",
            match=MatchCriteria(from_exact=addr0),
        )
        return InferenceResult(
            rule=rule,
            confidence="low",
            explanation=f"Using exact From value '{addr0}'. Consider selecting another sample to improve stability.",
        )

    raise ValueError("Could not infer a rule (missing List-Id and From headers).")
