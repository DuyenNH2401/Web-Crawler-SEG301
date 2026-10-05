import json
import re
from urllib.parse import parse_qs, urlparse

VIDEO_ID_RE = re.compile(r"^[\w-]{11}$")

def extract_video_id(url):
    url = url.strip()
    if VIDEO_ID_RE.match(url):
        return url  
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    candidate = None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        candidate = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        candidate = parse_qs(parsed.query).get("v", [None])[0]
        if not candidate:
            m = re.match(r"^/(?:shorts|live|embed)/([\w-]{11})", parsed.path)
            candidate = m.group(1) if m else None
    if candidate and VIDEO_ID_RE.match(candidate):
        return candidate
    return None


def extract_initial_data(html):
    """Lay object ytInitialData nhung trong HTML trang /watch."""
    m = re.search(
        r"(?:var\s+ytInitialData|window\[[\"']ytInitialData[\"']\])\s*=\s*",
        html,
    )
    if not m:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html, m.end())
    except json.JSONDecodeError:
        return None
    return data


def extract_innertube_config(html):
    key = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
    version = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
    return (key.group(1) if key else ""), (version.group(1) if version else "")


def extract_video_title(initial_data):
    for node in _iter_dicts(initial_data):
        primary = node.get("videoPrimaryInfoRenderer")
        if primary:
            return _text(primary.get("title"))
    return ""

def _iter_dicts(node):
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))


def find_token(node):
    for d in _iter_dicts(node):
        command = d.get("continuationCommand")
        if isinstance(command, dict) and isinstance(command.get("token"), str):
            return command["token"]
    return None


def find_comment_section_token(initial_data):
    for d in _iter_dicts(initial_data):
        section = d.get("itemSectionRenderer")
        if isinstance(section, dict) and "comment" in str(section.get("sectionIdentifier", "")):
            return find_token(section)
    return None


def _text(node):
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if "simpleText" in node:
        return node["simpleText"]
    return "".join(run.get("text", "") for run in node.get("runs", []))

def _entity_map(data):
    entities = {}
    mutations = (
        data.get("frameworkUpdates", {})
        .get("entityBatchUpdate", {})
        .get("mutations", [])
    )
    for mutation in mutations:
        payload = (mutation.get("payload") or {}).get("commentEntityPayload")
        if not payload:
            continue
        for key in (payload.get("key"), mutation.get("entityKey")):
            if key:
                entities[key] = payload
    return entities


def _from_legacy(renderer):
    author_id = (
        renderer.get("authorEndpoint", {})
        .get("browseEndpoint", {})
        .get("browseId", "")
    )
    return {
        "comment_id": renderer.get("commentId", ""),
        "content": _text(renderer.get("contentText")),
        "author_id": author_id,
        "author_name": _text(renderer.get("authorText")),
        "published_text": _text(renderer.get("publishedTimeText")),
        "like_text": _text(renderer.get("voteCount")),
    }


def _from_entity(payload):
    props = payload.get("properties", {})
    author = payload.get("author", {})
    toolbar = payload.get("toolbar", {})
    like_text = (
        toolbar.get("likeCountNotliked")
        or toolbar.get("likeCountA11y")
        or ""
    )
    return {
        "comment_id": props.get("commentId", ""),
        "content": (props.get("content") or {}).get("content", ""),
        "author_id": author.get("channelId", ""),
        "author_name": author.get("displayName", ""),
        "published_text": props.get("publishedTime", ""),
        "like_text": like_text,
    }


def _read_comment(holder, entities):
    legacy = holder.get("commentRenderer")
    if legacy:
        return _from_legacy(legacy)
    view = holder.get("commentViewModel")
    if view:
        view = view.get("commentViewModel", view)  # co luc bi boc 2 lop
        payload = entities.get(view.get("commentKey"))
        if payload:
            return _from_entity(payload)
        if view.get("commentId"):
            return {"comment_id": view["commentId"], "content": "", "author_id": "",
                    "author_name": "", "published_text": "", "like_text": ""}
    return None


def parse_next_response(data):
    entities = _entity_map(data)

    items = []
    for endpoint in data.get("onResponseReceivedEndpoints", []):
        container = (
            endpoint.get("reloadContinuationItemsCommand")
            or endpoint.get("appendContinuationItemsAction")
            or {}
        )
        items.extend(container.get("continuationItems", []))

    result = {"comments": [], "next_token": None, "sort_tokens": [], "total_text": ""}
    for item in items:
        if "commentsHeaderRenderer" in item:
            header = item["commentsHeaderRenderer"]
            result["total_text"] = _text(header.get("countText"))
            sub_items = (
                header.get("sortMenu", {})
                .get("sortFilterSubMenuRenderer", {})
                .get("subMenuItems", [])
            )
            result["sort_tokens"] = [find_token(entry) for entry in sub_items]
        elif "commentThreadRenderer" in item:
            thread = item["commentThreadRenderer"]
            holder = thread.get("comment") or thread
            comment = _read_comment(holder, entities)
            if comment:
                comment["reply_token"] = find_token(thread.get("replies"))
                result["comments"].append(comment)
        elif "commentRenderer" in item or "commentViewModel" in item:
            comment = _read_comment(item, entities)
            if comment:
                comment["reply_token"] = None
                result["comments"].append(comment)
        elif "continuationItemRenderer" in item:
            result["next_token"] = find_token(item["continuationItemRenderer"])
    return result
