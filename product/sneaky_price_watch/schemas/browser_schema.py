from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class BrowserConfig:
    """Schema for browser configuration."""
    user_agent: str
    proxy: str
    incognito: bool
    timeout: int

@dataclass
class PageData:
    """Schema for page data."""
    url: str
    content: str
    session_id: str
    fetched_at: str

@dataclass
class SessionData:
    """Schema for session data."""
    config: BrowserConfig
    created_at: str
    active: bool