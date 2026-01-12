from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .models import EmailMessage


@dataclass(frozen=True)
class Rule:
    name: str
    predicate: Callable[[EmailMessage], bool]
    action: str  # "print", "archive", "delete", "clickup"


class RulesEngine:
    def __init__(self, rules: Iterable[Rule]) -> None:
        self._rules = list(rules)

    def first_match(self, msg: EmailMessage) -> Optional[Rule]:
        for rule in self._rules:
            if rule.predicate(msg):
                return rule
        return None


def match_from_exact(addr: str) -> Callable[[EmailMessage], bool]:
    addr_l = addr.strip().lower()

    def _pred(msg: EmailMessage) -> bool:
        return msg.from_email.strip().lower() == addr_l

    return _pred


def subject_contains(needle: str) -> Callable[[EmailMessage], bool]:
    needle_l = needle.lower()

    def _pred(msg: EmailMessage) -> bool:
        return needle_l in (msg.subject or "").lower()

    return _pred


def subject_excludes(needle: str) -> Callable[[EmailMessage], bool]:
    needle_l = needle.lower()

    def _pred(msg: EmailMessage) -> bool:
        # Returns True if needle is NOT in subject
        return needle_l not in (msg.subject or "").lower()

    return _pred


def match_from_domain(domain: str) -> Callable[[EmailMessage], bool]:
    domain_l = domain.strip().lower()

    def _pred(msg: EmailMessage) -> bool:
        return f"@{domain_l}" in msg.from_email.lower()
    
    return _pred


def all_of(*preds: Callable[[EmailMessage], bool]) -> Callable[[EmailMessage], bool]:
    def _pred(msg: EmailMessage) -> bool:
        return all(p(msg) for p in preds)

    return _pred


def rule_from_config(pr: "PrintRule") -> Rule: 
    # lazy import to avoid circular dependency
    from .config import PrintRule 
    
    preds = []
    m = pr.match
    
    if m.from_exact:
        preds.append(match_from_exact(m.from_exact))
    
    if m.from_domain:
        preds.append(match_from_domain(m.from_domain))
        
    if m.subject_contains:
        preds.append(subject_contains(m.subject_contains))
        
    if m.subject_excludes:
        preds.append(subject_excludes(m.subject_excludes))
        
    if not preds:
        predicate = lambda m: False
    else:
        predicate = all_of(*preds)
        
    return Rule(name=pr.name, predicate=predicate, action=pr.action)
