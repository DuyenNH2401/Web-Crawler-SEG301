"""Chỉ phụ trách gửi HTTP request và tạo Beautiful Soup."""

import requests
from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, USER_AGENT


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_page(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")
