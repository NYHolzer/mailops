from mailops.rules import rule_from_config, subject_excludes, match_from_domain
from mailops.config import PrintRule, MatchCriteria
from mailops.models import EmailMessage, EmailContent

def test_subject_excludes():
    pred = subject_excludes("sale")
    
    # Matches if checking for NOT containing "sale"
    # So if subject is "Invoice", "sale" is NOT in it -> True
    msg = EmailMessage(
        message_id="1", thread_id=None, from_email="a@b.com", to_emails=(),
        subject="Invoice for order", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert pred(msg) is True
    
    # If subject is "Huge Sale", "sale" IS in it -> False
    msg2 = EmailMessage(
        message_id="2", thread_id=None, from_email="a@b.com", to_emails=(),
        subject="Huge Sale!", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert pred(msg2) is False

def test_match_from_domain():
    pred = match_from_domain("example.com")
    
    msg = EmailMessage(
        message_id="1", thread_id=None, from_email="User <user@example.com>", to_emails=(),
        subject="Hi", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert pred(msg) is True
    
    msg2 = EmailMessage(
        message_id="2", thread_id=None, from_email="user@other.com", to_emails=(),
        subject="Hi", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert pred(msg2) is False

def test_rule_factory_composition():
    # Rule: From example.com AND Subject excludes "Promo"
    pr = PrintRule(
        name="No Promos",
        action="archive",
        match=MatchCriteria(
            from_domain="example.com",
            subject_excludes="promo"
        )
    )
    
    rule = rule_from_config(pr)
    
    # Case 1: Matching domain, safe subject -> True
    msg1 = EmailMessage(
        message_id="1", thread_id=None, from_email="a@example.com", to_emails=(),
        subject="Update", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert rule.predicate(msg1) is True
    
    # Case 2: Matching domain, bad subject -> False
    msg2 = EmailMessage(
        message_id="2", thread_id=None, from_email="a@example.com", to_emails=(),
        subject="Summer Promo", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert rule.predicate(msg2) is False
    
    # Case 3: Wrong domain -> False
    msg3 = EmailMessage(
        message_id="3", thread_id=None, from_email="a@other.com", to_emails=(),
        subject="Update", date=None, snippet="", labels=frozenset(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    assert rule.predicate(msg3) is False
