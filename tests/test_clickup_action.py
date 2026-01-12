import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from mailops.actions.clickup_action import create_task_from_email, ClickUpConfig
from mailops.models import EmailMessage, EmailContent

def test_create_task_sends_request():
    msg = EmailMessage(
        message_id="1", thread_id="t1", from_email="u@example.com", to_emails=(),
        subject="Task Subject", date="2022-01-01", snippet="Snippet", labels=(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    config = ClickUpConfig(api_key="key", list_id="123")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"id":"task1"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        create_task_from_email(msg, config)
        
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://api.clickup.com/api/v2/list/123/task"
        assert req.get_header("Authorization") == "key"
        
        # Verify payload
        data = json.loads(req.data)
        assert data["name"] == "Task Subject"
        assert "Snippet" in data["description"]

def test_create_task_handles_error():
    msg = EmailMessage(
        message_id="1", thread_id="t1", from_email="u@example.com", to_emails=(),
        subject="Task", date=None, snippet="", labels=(),
        content=EmailContent(), has_attachments=False, attachment_count=0
    )
    config = ClickUpConfig(api_key="key", list_id="123")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        # Simulate HTTP Error
        err = urllib.error.HTTPError(
            url="url", code=401, msg="Unauthorized", hdrs={}, fp=MagicMock()
        )
        err.fp.read.return_value = b"Unauthorized"
        mock_urlopen.side_effect = err
        
        with pytest.raises(urllib.error.HTTPError):
            create_task_from_email(msg, config)
