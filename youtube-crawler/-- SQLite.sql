-- SQLite
SELECT id, author_name, content, like_count, created_at
FROM comments WHERE post_id = 'SGZkBoBsxsk' ORDER BY like_count DESC;

SELECT post_id, COUNT(*) AS tong,
       SUM(parent_id = 'ROOT') AS goc, SUM(parent_id <> 'ROOT') AS reply
FROM comments GROUP BY post_id;

SELECT author_name, author_id, COUNT(*) AS so_comment
FROM comments GROUP BY author_id ORDER BY so_comment DESC LIMIT 20;

SELECT id, parent_id, author_name, content FROM comments
WHERE comment_id = 'UgxAbC...' OR parent_id = 'UgxAbC...';

SELECT content, COUNT(*) AS n FROM comments GROUP BY content HAVING n > 1 ORDER BY n DESC;