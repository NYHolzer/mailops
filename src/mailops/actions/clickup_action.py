import os
import logging
from typing import Optional
from dataclasses import dataclass
import json
import urllib.request
import urllib.error

from ..models import EmailMessage

logger = logging.getLogger(__name__)

@dataclass
class ClickUpConfig:
    api_key: str
    list_id: str

def get_clickup_config() -> Optional[ClickUpConfig]:
    api_key = os.environ.get("CLICKUP_API_KEY")
    list_id = os.environ.get("CLICKUP_LIST_ID")
    
    if not api_key or not list_id:
        logger.warning("CLICKUP_API_KEY or CLICKUP_LIST_ID not set. ClickUp action specific configuration missing.")
        return None
    return ClickUpConfig(api_key=api_key, list_id=list_id)

def create_task_from_email(msg: EmailMessage, config: ClickUpConfig) -> None:
    """
    Create a task in ClickUp for the given email.
    """
    url = f"https://api.clickup.com/api/v2/list/{config.list_id}/task"
    
    # Basic description from snippet or we could fetch body if needed.
    # For now, using snippet and metadata.
    description = (
        f"From: {msg.from_email}\n"
        f"Date: {msg.date}\n"
        f"Subject: {msg.subject}\n\n"
        f"{msg.snippet}\n\n"
        f"(Created via MailOps automation)"
    )
    
    payload = {
        "name": msg.subject or "(No Subject)",
        "description": description,
        "status": "OPEN", # Default status
        # "priority": 3, # Normal
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", config.api_key)
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req) as response:
            if 200 <= response.status < 300:
                res_body = response.read()
                logger.info(f"Successfully created ClickUp task for message {msg.message_id}")
                logger.debug(f"ClickUp response: {res_body}")
            else:
                logger.error(f"ClickUp API returned unexpected status: {response.status}")
                
    except urllib.error.HTTPError as e:
        logger.error(f"ClickUp API failed: {e.code} - {e.read().decode('utf-8')}")
        raise
    except Exception as e:
        logger.error(f"Failed to create ClickUp task: {e}")
        raise
