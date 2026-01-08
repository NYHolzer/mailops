from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional 

from .models import EmailMessage

@dataclass(frozen=True)
class Rule:
    name: str
    condition: Callable[[EmailMessage], bool]
    action: str #e.g. "print", "archive", "delete", "clickup"

class RulesEngine:
    def __init__(self, rules):
        self._rules = list(rules)

    def first_match(self, msg):
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
        return needle_l in msg.subject.lower()
    
    return _pred

def all_of (*preds: Callable[[EmailMessage], bool]) -> Callable[[EmailMessage], bool]:
    def _pred(msg: EmailMessage) -> bool:
        return all(p(msg) for p in preds)
    
    return _pred