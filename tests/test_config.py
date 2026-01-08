from __future__ import annotations

import json
from pathlib import Path

import pytest

from mailops.config import AppConfig, MatchCriteria, PrintRule, add_rule, load_config, save_config


def test_load_config_returns_default_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("MAILOPS_CONFIG_PATH", str(cfg_path))

    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.printer_name == "HP577dw"
    assert cfg.print_rules == ()


def test_save_and_load_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("MAILOPS_CONFIG_PATH", str(cfg_path))

    rule = PrintRule(
        name="1440",
        action="print",
        match=MatchCriteria(header_list_id_contains="join1440", requires_unsubscribe_header=True),
    )
    cfg_in = AppConfig(printer_name="HP577dw", print_rules=(rule,))

    saved_path = save_config(cfg_in)
    assert saved_path.exists()

    cfg_out = load_config()
    assert cfg_out.printer_name == "HP577dw"
    assert len(cfg_out.print_rules) == 1
    assert cfg_out.print_rules[0].name == "1440"
    assert cfg_out.print_rules[0].action == "print"
    assert cfg_out.print_rules[0].match.header_list_id_contains == "join1440"
    assert cfg_out.print_rules[0].match.requires_unsubscribe_header is True


def test_add_rule_replaces_by_name_case_insensitive():
    cfg = AppConfig(printer_name="HP577dw", print_rules=())

    r1 = PrintRule(
        name="OpenSourceIntel",
        action="print",
        match=MatchCriteria(from_domain="example.com"),
    )
    cfg2 = add_rule(cfg, r1)
    assert len(cfg2.print_rules) == 1
    assert cfg2.print_rules[0].name == "OpenSourceIntel"

    r2 = PrintRule(
        name="opensourceintel",  # different case, should replace
        action="print",
        match=MatchCriteria(header_list_id_contains="list.example.com"),
    )
    cfg3 = add_rule(cfg2, r2)
    assert len(cfg3.print_rules) == 1
    assert cfg3.print_rules[0].name == "opensourceintel"
    assert cfg3.print_rules[0].match.header_list_id_contains == "list.example.com"


def test_load_config_rejects_invalid_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("MAILOPS_CONFIG_PATH", str(cfg_path))

    bad = {
        "printer_name": "HP577dw",
        "print_rules": [
            {
                "name": "BadRule",
                "action": "explode",
                "match": {"from_exact": "x@example.com"},
            }
        ],
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError) as e:
        load_config()
    assert "invalid action" in str(e.value).lower()


def test_load_config_rejects_missing_rule_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("MAILOPS_CONFIG_PATH", str(cfg_path))

    bad = {
        "printer_name": "HP577dw",
        "print_rules": [
            {
                "action": "print",
                "match": {"from_exact": "x@example.com"},
            }
        ],
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError) as e:
        load_config()
    assert "name" in str(e.value).lower()
