from __future__ import annotations

from mailops.infer import infer_print_rule


def test_infer_prefers_list_id_high_confidence():
    headers = [
        {
            "From": "1440 Daily Digest <dailydigest@email.join1440.com>",
            "List-Id": "<daily.join1440.com>",
            "List-Unsubscribe": "<mailto:unsubscribe@join1440.com>",
        }
    ]
    res = infer_print_rule("1440", headers)
    assert res.confidence == "high"
    assert res.rule.match.header_list_id_contains is not None
    assert res.rule.match.requires_unsubscribe_header is True


def test_infer_falls_back_to_from_domain_when_address_present():
    headers = [{"From": "news@example.com"}]
    res = infer_print_rule("DomainOnly", headers)
    assert res.confidence == "medium"
    assert res.rule.match.from_domain == "example.com"


def test_infer_falls_back_to_from_exact_when_no_email_present():
    headers = [{"From": "Some Newsletter"}]  # no email address
    res = infer_print_rule("ExactOnly", headers)
    assert res.confidence == "low"
    assert res.rule.match.from_exact == "Some Newsletter"
