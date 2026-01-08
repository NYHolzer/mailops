from mailops.models import EmailContent, EmailMessage
from mailops.rules import Rule, RulesEngine, all_of, match_from_exact, subject_contains


def test_rules_engine_first_match():
    msg = EmailMessage(
        message_id="abc",
        thread_id=None,
        from_email="orders@example.com",
        to_emails=("me@example.com",),
        subject="Order #12345",
        date=None,
        snippet="",
        labels=frozenset({"INBOX", "UNREAD"}),
        content=EmailContent(text="Thanks for your order"),
        has_attachments=False,
        attachment_count=0,
    )

    rules = RulesEngine(
        [
            Rule("print_invoices", all_of(match_from_exact("billing@example.com"), subject_contains("invoice")), "print"),
            Rule("archive_orders", all_of(match_from_exact("orders@example.com"), subject_contains("order")), "archive"),
        ]
    )

    r = rules.first_match(msg)
    assert r is not None
    assert r.name == "archive_orders"
    assert r.action == "archive"
