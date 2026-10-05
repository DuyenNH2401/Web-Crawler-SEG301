-- Schema chung cua nhom (database chinh - PostgreSQL).
-- File CSV xuat tu crawler co DUNG cac cot nay (tru `id`, de DB tu sinh).

CREATE TABLE IF NOT EXISTS comments (
    id            BIGSERIAL PRIMARY KEY,

    platform      VARCHAR(20)  NOT NULL,
    comment_id    VARCHAR(255) NOT NULL,
    content       TEXT         NOT NULL,

    author_id     VARCHAR(255) NOT NULL,
    author_name   VARCHAR(255) NOT NULL,

    parent_id     VARCHAR(255) NOT NULL,
    post_id       VARCHAR(255) NOT NULL,
    comment_url   TEXT         NOT NULL,

    created_at    TIMESTAMP    NOT NULL,
    like_count    INTEGER      NOT NULL DEFAULT 0,

    collected_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(platform, comment_id)
);

-- Import CSV vao database chinh, bo qua comment da co (trung platform + comment_id):
--
--   CREATE TEMP TABLE staging (LIKE comments INCLUDING DEFAULTS);
--   \copy staging(platform, comment_id, content, author_id, author_name, parent_id,
--                 post_id, comment_url, created_at, like_count, collected_at)
--         FROM 'youtube.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
--   INSERT INTO comments(platform, comment_id, content, author_id, author_name, parent_id,
--                        post_id, comment_url, created_at, like_count, collected_at)
--   SELECT platform, comment_id, content, author_id, author_name, parent_id,
--          post_id, comment_url, created_at, like_count, collected_at
--   FROM staging
--   ON CONFLICT (platform, comment_id) DO NOTHING;
