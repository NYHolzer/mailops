from mailops.models import EmailMessage
from mailops.rules import Rule, RuleEngine, all_of, match_from_exact, subject_contains

def test_rules_engine_first_match() -> None:
    msg = EmailMessage(
        message_id="123",
        thread_id=None,
        from_email="orders@example.com",
        subject="Order #12345"
        date=None,
        snippet="",
        body_text-"Thank you for your order!",
    )

    rules = RuleEngine(
        [
            Rule("print_invoices", all_of(match_from_exact("billing@example.com"), subject_contains("Invoice")), "print"),
            Rule("archive_orders", all_of(match_from_exact("orders@example.com"), subject_contains("Order")), "archive"),
        ]
    )

    r = rules.first_match(msg)
    assert r is not None
    assert r.name == "archive_orders"
    assert r.action == "archive"