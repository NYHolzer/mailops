from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

ActionType = Literal["print", "archive", "delete", "clickup"]


def _default_config_path() -> Path:
    """
    Default to a per-user config location so the app is shareable and does not
    require cloning the repo into a specific folder structure.
    """
    # Allow override for power users and for future frontend deployments.
    override = os.environ.get("MAILOPS_CONFIG_PATH")
    if override:
        return Path(override).expanduser()

    # Linux/WSL-friendly default (~/.config/...)
    return Path.home() / ".config" / "mailops" / "config.json"


@dataclass(frozen=True)
class MatchCriteria:
    """
    Match criteria is intentionally flexible and JSON-serializable.
    For newsletters we will commonly use:
      - header_list_id_contains
      - requires_unsubscribe_header
      - from_domain
      - from_exact
      - subject_contains
    """
    header_list_id_contains: Optional[str] = None
    requires_unsubscribe_header: bool = False
    from_domain: Optional[str] = None
    from_exact: Optional[str] = None
    subject_contains: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "header_list_id_contains": self.header_list_id_contains,
            "requires_unsubscribe_header": self.requires_unsubscribe_header,
            "from_domain": self.from_domain,
            "from_exact": self.from_exact,
            "subject_contains": self.subject_contains,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "MatchCriteria":
        return MatchCriteria(
            header_list_id_contains=d.get("header_list_id_contains"),
            requires_unsubscribe_header=bool(d.get("requires_unsubscribe_header", False)),
            from_domain=d.get("from_domain"),
            from_exact=d.get("from_exact"),
            subject_contains=d.get("subject_contains"),
        )


@dataclass(frozen=True)
class PrintRule:
    name: str
    action: ActionType
    match: MatchCriteria

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "action": self.action, "match": self.match.to_dict()}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PrintRule":
        name = d.get("name")
        action = d.get("action")
        match = d.get("match")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Rule must have a non-empty 'name' string.")
        if action not in ("print", "archive", "delete", "clickup"):
            raise ValueError(f"Rule '{name}' has invalid action: {action!r}")
        if not isinstance(match, dict):
            raise ValueError(f"Rule '{name}' must have a 'match' object.")

        return PrintRule(name=name.strip(), action=action, match=MatchCriteria.from_dict(match))


@dataclass(frozen=True)
class AppConfig:
    printer_name: str
    print_rules: tuple[PrintRule, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "printer_name": self.printer_name,
            "print_rules": [r.to_dict() for r in self.print_rules],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "AppConfig":
        printer_name = d.get("printer_name", "HP577dw")
        if not isinstance(printer_name, str) or not printer_name.strip():
            raise ValueError("Config 'printer_name' must be a non-empty string.")

        rules_raw = d.get("print_rules", [])
        if not isinstance(rules_raw, list):
            raise ValueError("Config 'print_rules' must be a list.")

        rules = tuple(PrintRule.from_dict(x) for x in rules_raw)
        return AppConfig(printer_name=printer_name.strip(), print_rules=rules)


def load_config(path: Optional[Path] = None) -> AppConfig:
    p = path or _default_config_path()
    if not p.exists():
        # Return a safe default config if none exists yet.
        return AppConfig(printer_name="HP577dw", print_rules=())

    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config file root must be a JSON object.")
    return AppConfig.from_dict(data)


def save_config(cfg: AppConfig, path: Optional[Path] = None) -> Path:
    p = path or _default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def add_rule(cfg: AppConfig, rule: PrintRule) -> AppConfig:
    """
    Add or replace a rule by name (case-insensitive).
    """
    existing = {r.name.lower(): r for r in cfg.print_rules}
    existing[rule.name.lower()] = rule
    rules_sorted = tuple(existing.values())
    return AppConfig(printer_name=cfg.printer_name, print_rules=rules_sorted)
