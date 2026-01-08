from __future__ import annotations

from mailops.search import SearchFilters, build_gmail_query


def test_default_filters_build_inbox_unread_query():
    q = build_gmail_query(SearchFilters())
    assert q == "in:inbox is:unread"


def test_text_search_only():
    q = build_gmail_query(SearchFilters(text="1440"))
    assert q == "in:inbox is:unread 1440"


def test_from_filter():
    q = build_gmail_query(SearchFilters(from_addr="newsletter@join1440.com"))
    assert q == "in:inbox is:unread from:newsletter@join1440.com"


def test_newer_than_days():
    q = build_gmail_query(SearchFilters(newer_than_days=7))
    assert q == "in:inbox is:unread newer_than:7d"


def test_combined_filters():
    q = build_gmail_query(
        SearchFilters(
            text="opensource",
            from_addr="opensourceintel@example.com",
            newer_than_days=30,
        )
    )
    assert (
        q
        == "in:inbox is:unread from:opensourceintel@example.com newer_than:30d opensource"
    )


def test_include_read_messages():
    q = build_gmail_query(SearchFilters(unread_only=False))
    assert q == "in:inbox"


def test_include_all_mail():
    q = build_gmail_query(SearchFilters(inbox_only=False))
    assert q == "is:unread"


def test_include_all_mail_and_read():
    q = build_gmail_query(SearchFilters(inbox_only=False, unread_only=False))
    assert q == ""
