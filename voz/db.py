import sqlite3


def init_db(path="comments.db"):
  conn = sqlite3.connect(path)
  conn.execute("""
    CREATE TABLE IF NOT EXISTS comments (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      platform     VARCHAR(20)  NOT NULL,
      comment_id   VARCHAR(255) NOT NULL,
      content      TEXT         NOT NULL,
      author_id    VARCHAR(255) NOT NULL,
      author_name  VARCHAR(255) NOT NULL,
      parent_id    VARCHAR(255) NOT NULL,
      post_id      VARCHAR(255) NOT NULL,
      created_at   TIMESTAMP    NOT NULL,
      like_count   INTEGER      NOT NULL DEFAULT 0,
      collected_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(platform, comment_id)
    )
  """)
  return conn


def save_comments(conn, rows):
  conn.executemany("""
    INSERT OR IGNORE INTO comments
      (platform, comment_id, content, author_id, author_name, parent_id, post_id, created_at, like_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  """, rows)
  conn.commit()