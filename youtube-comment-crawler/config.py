import os
from datetime import timedelta, timezone

PLATFORM = "youtube"

REQUEST_TIMEOUT = 20 
REQUEST_DELAY = 0.3   
MAX_RETRIES = 3       

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

LANGUAGE = "en"
REGION = "VN"

DEFAULT_SORT = "newest"
INCLUDE_REPLIES = True

MAX_COMMENTS_PER_VIDEO = 0 # lấy hết cả comment cả reply

MIN_WORDS = 0

UNKNOWN = "UNKNOWN"   
ROOT = "ROOT"         

TIMEZONE = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

EXPORT_COLUMNS = [
    "platform",
    "comment_id",
    "content",
    "author_id",
    "author_name",
    "parent_id",
    "post_id",
    "comment_url",
    "created_at",
    "like_count",
    "collected_at",
]


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "comments.db")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")


def print_configuration(sort, include_replies, max_comments, min_words, db_path=None):
    print("=" * 11 + " CRAWLER CONFIGURATION " + "=" * 11)
    print()
    print(f"Platform        : {PLATFORM}")
    print(f"Sort            : {sort}")
    print(f"Include Replies : {include_replies}")
    print(f"Max / Video     : {max_comments or 'ALL'}")
    print(f"Min Words       : {min_words}")
    print(f"Request Delay   : {REQUEST_DELAY} second(s)")
    print(f"Timezone        : {TIMEZONE.tzname(None)}")
    print(f"Database        : {db_path or DB_PATH}")
    print("=" * 45)
    print()
