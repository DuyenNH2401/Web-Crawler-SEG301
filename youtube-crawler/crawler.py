import config
from normalizer import compile_keywords, content_key, count_words, match_keywords, now, to_record
from youtube_client import YouTubeClient, YouTubeError
from youtube_parser import (
    extract_video_id,
    extract_video_title,
    find_comment_section_token,
    parse_next_response,
)


class _LimitReached(Exception):
    pass


class YouTubeCommentCrawler:
    def __init__(self, db, client=None):
        self.db = db
        self.client = client or YouTubeClient()
        self.stats = {
            "videos_ok": 0,
            "videos_failed": 0,
            "comments_saved": 0,
            "replies_saved": 0,
            "skipped_short": 0,
            "skipped_keyword": 0,
            "duplicates": 0,
            "duplicate_content": 0,
            "already_in_db": 0,
        }

    def crawl_video(
        self,
        url,
        max_comments=config.MAX_COMMENTS_PER_VIDEO,
        sort=config.DEFAULT_SORT,
        include_replies=config.INCLUDE_REPLIES,
        min_words=config.MIN_WORDS,
        keywords=None,
        dedup_content=config.DEDUP_CONTENT,
    ):

        keyword_patterns = compile_keywords(keywords)
        video_id = extract_video_id(url)
        if not video_id:
            print(f"[SKIP] Khong phai link video YouTube: {url}")
            self.stats["videos_failed"] += 1
            return 0

        collected_at = now()
        seen_ids = set()
        saved = {"total": 0}

        existing_ids = {cid for cid, _, _ in self.db.get_post_comments(video_id)}

        def make_content_key(author_id, content):
            author = author_id if dedup_content == "author" else ""
            return (author, content_key(content))

        content_owner = {}
        if dedup_content in ("author", "all", "global"):
            rows = (self.db.get_all_comments() if dedup_content == "global"
                    else self.db.get_post_comments(video_id))
            for cid, author_id, content in rows:
                content_owner.setdefault(make_content_key(author_id, content), cid)

        def save(raw_list, parent_id):
            batch = []
            for raw in raw_list:
                record = to_record(raw, video_id, parent_id, collected_at)
                if record is None:
                    continue
                if record["comment_id"] in seen_ids:
                    self.stats["duplicates"] += 1
                    continue
                if record["comment_id"] in existing_ids:
                    seen_ids.add(record["comment_id"])
                    self.stats["already_in_db"] += 1
                    continue
                if min_words and count_words(record["content"]) < min_words:
                    self.stats["skipped_short"] += 1
                    continue
                if keyword_patterns and not match_keywords(record["content"], keyword_patterns):
                    seen_ids.add(record["comment_id"])
                    self.stats["skipped_keyword"] += 1
                    continue
                if dedup_content in ("author", "all", "global"):
                    key = make_content_key(record["author_id"], record["content"])
                    owner = content_owner.get(key)
                    if owner is not None and owner != record["comment_id"]:
                        seen_ids.add(record["comment_id"])
                        self.stats["duplicate_content"] += 1
                        continue
                    content_owner[key] = record["comment_id"]
                if max_comments and saved["total"] + len(batch) >= max_comments:
                    break
                seen_ids.add(record["comment_id"])
                batch.append(record)
            if batch:
                inserted = self.db.insert_comments(batch)
                saved["total"] += inserted
                key = "comments_saved" if parent_id is None else "replies_saved"
                self.stats[key] += inserted
                self.stats["already_in_db"] += len(batch) - inserted
            if max_comments and saved["total"] >= max_comments:
                raise _LimitReached()

        try:
            initial_data = self.client.fetch_watch_page(video_id)
            title = extract_video_title(initial_data)
            print(f"[VIDEO] {video_id} | {title[:70]}")

            token = find_comment_section_token(initial_data)
            if not token:
                raise YouTubeError("Video tat binh luan hoac YouTube khong tra phan binh luan.")

            page = parse_next_response(self.client.next(token))
            if page["total_text"]:
                print(f"        YouTube hien thi: {page['total_text']}")
            sort_index = 1 if sort == "newest" else 0
            if len(page["sort_tokens"]) > sort_index and page["sort_tokens"][sort_index]:
                page = parse_next_response(self.client.next(page["sort_tokens"][sort_index]))

            seen_tokens = {token}
            page_no = 1
            while True:
                save(page["comments"], None)
                if include_replies:
                    for comment in page["comments"]:
                        if comment.get("reply_token"):
                            self._crawl_replies(comment, save)
                print(f"        trang {page_no}: tong da luu {saved['total']}")

                token = page["next_token"]
                if not token or token in seen_tokens:
                    break
                seen_tokens.add(token)
                page = parse_next_response(self.client.next(token))
                page_no += 1
        except _LimitReached:
            print(f"        dat gioi han {max_comments} comment.")
        except YouTubeError as e:
            print(f"[ERROR] {video_id}: {e}")
            if saved["total"] == 0:
                self.stats["videos_failed"] += 1
                return 0

        self.stats["videos_ok"] += 1
        print(f"[DONE]  {video_id}: luu {saved['total']} comment (ca reply)\n")
        return saved["total"]

    def _crawl_replies(self, parent, save):
        token = parent["reply_token"]
        seen = set()
        while token and token not in seen:
            seen.add(token)
            page = parse_next_response(self.client.next(token))
            save(page["comments"], parent["comment_id"])
            token = page["next_token"]
