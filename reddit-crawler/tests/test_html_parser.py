import tempfile
import unittest
from pathlib import Path

from reddit_app.database import Store
from reddit_app.crawler import crawl
from reddit_app.html_parser import clean_text_from_html, parse_comments_html, parse_posts_html
from reddit_app.main import build_parser


SAMPLE_SUBREDDIT_HTML = """
<html>
<body>
  <shreddit-post id="t3_post123" author="author_one" permalink="/r/test/comments/post123/my_post/" comment-count="5">
    <a slot="title">Tiêu đề bài viết thử nghiệm</a>
  </shreddit-post>
  <shreddit-post id="t3_post456" author="author_two" permalink="/r/test/comments/post456/another/" comment-count="0">
    <div slot="title">Bài viết thứ hai</div>
  </shreddit-post>
</body>
</html>
"""

SAMPLE_POST_HTML = """
<html>
<body>
  <shreddit-comment thingid="t1_comm1" author="user_a" score="15" postid="t3_post123" permalink="/r/test/comments/post123/my_post/comm1/">
    <div id="t1_comm1-post-rtjson-content">
      <p>Bình luận tiếng Việt đầu tiên.</p>
      <p>Dòng thứ hai của bình luận.</p>
    </div>
  </shreddit-comment>
  <shreddit-comment thingid="t1_comm2" author="user_b" score="-2" postid="t3_post123" permalink="/r/test/comments/post123/my_post/comm2/">
    <div slot="comment">
      <p>Bình luận phản hồi thứ hai.</p>
    </div>
  </shreddit-comment>
</body>
</html>
"""


class HtmlParserTests(unittest.TestCase):
    def test_parse_posts_html(self):
        posts = parse_posts_html(SAMPLE_SUBREDDIT_HTML)
        self.assertEqual(len(posts), 2)
        
        self.assertEqual(posts[0]["id"], "post123")
        self.assertEqual(posts[0]["post_id"], "t3_post123")
        self.assertEqual(posts[0]["author"], "author_one")
        self.assertEqual(posts[0]["title"], "Tiêu đề bài viết thử nghiệm")
        self.assertEqual(posts[0]["comment_count"], 5)
        self.assertEqual(posts[0]["permalink"], "/r/test/comments/post123/my_post/")

        self.assertEqual(posts[1]["id"], "post456")
        self.assertEqual(posts[1]["author"], "author_two")
        self.assertEqual(posts[1]["title"], "Bài viết thứ hai")

    def test_parse_comments_html(self):
        comments, unexpanded = parse_comments_html(SAMPLE_POST_HTML, subreddit="test")
        self.assertEqual(len(comments), 2)
        self.assertEqual(unexpanded, 0)

        c1 = comments[0]
        self.assertEqual(c1["comment_id"], "comm1")
        self.assertEqual(c1["author_name"], "user_a")
        self.assertEqual(c1["score"], 15)
        self.assertEqual(c1["like_count"], 15)
        self.assertEqual(c1["post_id"], "t3_post123")
        self.assertEqual(c1["subreddit"], "test")
        self.assertIn("Bình luận tiếng Việt đầu tiên.", c1["content"])
        self.assertIn("Dòng thứ hai của bình luận.", c1["content"])
        self.assertEqual(c1["comment_url"], "https://www.reddit.com/r/test/comments/post123/my_post/comm1/")

        c2 = comments[1]
        self.assertEqual(c2["comment_id"], "comm2")
        self.assertEqual(c2["score"], -2)
        self.assertEqual(c2["content"], "Bình luận phản hồi thứ hai.")

    def test_clean_text_from_html(self):
        self.assertEqual(clean_text_from_html(None), "")


class HtmlCrawlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")
        self.addCleanup(self.store.close)

    def test_crawl_mode_html(self):
        class MockHtmlReddit:
            def new_posts_html(self, subreddit, limit=100):
                return [{"id": "p1", "permalink": "/r/test/comments/p1/title/"}]

            def comments_html(self, subreddit, post_id, permalink=None):
                comments, _ = parse_comments_html(SAMPLE_POST_HTML, subreddit=subreddit)
                return comments, 0

        res = crawl(MockHtmlReddit(), self.store, "test", max_comments=2, mode="html")
        self.assertEqual(res["mode"], "html")
        self.assertEqual(res["saved"], 2)
        self.assertEqual(res["posts"], 1)
        self.assertEqual(len(self.store.ids()), 2)

    def test_cli_parser_mode_argument(self):
        parser = build_parser()
        args_json = parser.parse_args(["crawl", "--cookies-file", "cookie.txt", "--subreddit", "python", "--max-comments", "10"])
        self.assertEqual(args_json.mode, "json")

        args_html = parser.parse_args(["crawl", "--cookies-file", "cookie.txt", "--subreddit", "python", "--max-comments", "10", "--mode", "html"])
        self.assertEqual(args_html.mode, "html")


if __name__ == "__main__":
    unittest.main()
