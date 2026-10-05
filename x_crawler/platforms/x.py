"""Collect X replies through the official X API v2 search endpoints."""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from models import Comment


API_BASE = "https://api.x.com/2/tweets/search"
POST_ID_PATTERN = re.compile(r"^[0-9]{1,19}$")


def parse_post_id(value: str) -> str:
    """Accept a numeric ID or an X/Twitter status URL, never an arbitrary URL."""
    value = value.strip()
    if POST_ID_PATTERN.fullmatch(value):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "x.com", "www.x.com", "twitter.com", "www.twitter.com",
        "mobile.twitter.com",
    ):
        raise ValueError(f"Invalid X post URL or ID: {value}")
    parts = parsed.path.strip("/").split("/")
    if (len(parts) == 4 and parts[:3] == ["i", "web", "status"]
            and POST_ID_PATTERN.fullmatch(parts[3])):
        return parts[3]
    if len(parts) != 3 or parts[1] != "status" or not POST_ID_PATTERN.fullmatch(parts[2]):
        raise ValueError(f"Invalid X post URL or ID: {value}")
    return parts[2]


def _utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp has no time zone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def map_reply(post: dict, users: dict, root_id: str, collected_at: str) -> Comment | None:
    """Map a search result to the shared schema; ignore non-replies or bad IDs."""
    comment_id = str(post.get("id") or "")
    if not POST_ID_PATTERN.fullmatch(comment_id) or comment_id == root_id:
        return None
    if str(post.get("conversation_id") or "") != root_id:
        return None
    references = post.get("referenced_posts") or post.get("referenced_tweets") or []
    parent = next((str(ref.get("id")) for ref in references
                   if ref.get("type") == "replied_to" and ref.get("id")), None)
    if not parent or not POST_ID_PATTERN.fullmatch(parent):
        return None
    try:
        created_at = _utc_timestamp(post["created_at"])
    except (KeyError, TypeError, ValueError):
        return None
    author_id = str(post.get("author_id") or "UNKNOWN")
    user = users.get(author_id, {})
    name = user.get("name") or user.get("username") or post.get("username") or "UNKNOWN"
    username = user.get("username") or post.get("username")
    url = (f"https://x.com/{username}/status/{comment_id}" if username
           else f"https://x.com/i/web/status/{comment_id}")
    metrics = post.get("public_metrics") or {}
    try:
        likes = max(0, int(metrics.get("like_count") or 0))
    except (ValueError, TypeError):
        likes = 0
    note = post.get("note_post") or post.get("note_tweet") or {}
    return Comment(
        platform="x", comment_id=comment_id,
        content=note.get("text") or post.get("text") or "",
        author_id=author_id, author_name=str(name),
        parent_id="ROOT" if parent == root_id else parent,
        post_id=root_id, comment_url=url, created_at=created_at,
        like_count=likes, collected_at=collected_at,
    )


class XCommentsCrawler:
    def __init__(self, bearer_token: str, *, session: requests.Session | None = None,
                 timeout: int = 20):
        if not bearer_token:
            raise ValueError("X_BEARER_TOKEN is required")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})
        self.timeout = timeout

    def crawl(self, post_id: str, *, archive: bool = False,
              max_comments: int = 1000) -> list[Comment]:
        post_id = parse_post_id(post_id)
        if max_comments < 1:
            raise ValueError("max_comments must be at least 1")
        endpoint = f"{API_BASE}/{'all' if archive else 'recent'}"
        params = {
            "query": f"conversation_id:{post_id} is:reply -is:retweet",
            "max_results": min(100, max(10, max_comments)),
            "post.fields": "created_at,conversation_id,public_metrics,note_post",
            "expansions": "author_id,referenced_posts",
            "user.fields": "name,username",
        }
        found: dict[str, Comment] = {}
        seen_tokens: set[str] = set()
        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        while len(found) < max_comments:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
            if response.status_code == 429:
                raise RuntimeError("X API rate limit reached (HTTP 429). Retry after the reset window.")
            try:
                response.raise_for_status()
            except requests.HTTPError as error:
                raise RuntimeError(f"X API request failed (HTTP {response.status_code})") from error
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(f"X API returned partial errors: {payload['errors']}")
            users = {str(user["id"]): user for user in payload.get("includes", {}).get("users", [])
                     if user.get("id")}
            for post in payload.get("data") or []:
                comment = map_reply(post, users, post_id, collected_at)
                if comment:
                    found[comment.comment_id] = comment
                    if len(found) >= max_comments:
                        break
            token = (payload.get("meta") or {}).get("next_token")
            if not token or token in seen_tokens:
                break
            seen_tokens.add(token)
            params["pagination_token"] = token
        return list(found.values())

    def close(self) -> None:
        self.session.close()
