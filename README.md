# Cào bình luận X, Reddit, YouTube, TikTok và Threads

Dự án có năm crawler trong `x_crawler/`, `seg301_crawler_reddit/`, `youtube-comment-crawler/`, `tiktok_crawler/` và `Crawl_Thread/`. Chạy từ thư mục gốc qua `main.py`; bình luận của cả năm được lưu trong **một bảng `comments`** ở `data/comments.db`, với khóa duy nhất `(platform, comment_id)`. Chạy `python main.py migrate` để nhập thêm dữ liệu từ các database cũ mà không tạo bản sao bình luận.

```powershell
python main.py x --post "https://x.com/username/status/1234567890123456789"
python main.py reddit crawl-public --subreddit python --max-comments 100 --max-posts 10
python main.py youtube --url "https://www.youtube.com/watch?v=VIDEO_ID" --max-comments 100
python main.py tiktok "https://www.tiktok.com/@username/video/VIDEO_ID" --max 100 --replies --channel chrome
python main.py threads crawl --url "https://www.threads.com/@username/post/POST_ID" --max-pages 20 --headed
python main.py reddit stats
```

Thêm `--db D:\duong-dan\comments.db` ngay sau `main.py` để dùng file SQLite khác. Xem tham số qua `python main.py x -h`, `reddit -h`, `youtube -h`, `tiktok -h`, `threads -h` (đều đặt sau `main.py`). Lệnh X cũ `python main.py --post ...` vẫn chạy.

`purge` của Reddit chỉ xóa bản ghi Reddit. Threads vẫn dùng `Crawl_Thread/data/.../dataset.sqlite3` để lưu tiến độ, trang HTML và quan hệ giữa bình luận với bài viết; sau mỗi lệnh Threads chạy qua `main.py` gốc, bình luận được đồng bộ vào database chung. Khi một bình luận Threads xuất hiện trong nhiều bài, bảng `threads_comment_context` trong database chung giữ toàn bộ các quan hệ đó. Database cũ của TikTok và Threads được giữ nguyên để đối chiếu.

## Cài đặt

Yêu cầu Python 3.10+ và Google Chrome đã cài trên máy. Chỉ cần cài thư viện Python:

```powershell
python -m pip install -r requirements.txt
```

Hãy dùng cùng một môi trường Python khi cài thư viện và chạy `main.py` (ví dụ môi trường `(AI)` của bạn). Threads cần `PyYAML`, `httpx`, `beautifulsoup4` và `lxml`; các thư viện này đã có trong `requirements.txt`. Với Threads ở chế độ trình duyệt, cài Chromium một lần bằng `python -m playwright install chromium`.

Chương trình mặc định dùng Chrome đã cài (`--browser-channel chrome`) với thư mục phiên riêng; không dùng hồ sơ Chrome bạn đang duyệt hằng ngày. Nếu muốn dùng Chromium của Playwright, chạy `python -m playwright install chromium` rồi thêm `--browser-channel chromium` vào lệnh cào.

## Cào qua cửa sổ trình duyệt (mặc định)

Mở PowerShell trong thư mục dự án và chạy:

```powershell
python main.py --post "https://x.com/username/status/1234567890123456789"
```

Chương trình dùng phiên trong `data/x_browser_profile/`. Nếu muốn nạp cookie từ tệp, thêm `--cookie-file data/x_cookies.json` một cách tường minh. Bạn có thể chạy ẩn cửa sổ khi hồ sơ đã đăng nhập:

```powershell
python main.py --post "https://x.com/username/status/1234567890123456789" --headless
```

Chrome vẫn chạy ở nền để đọc giao diện X. Nếu hồ sơ chưa đăng nhập, hãy chạy không có `--headless`, đăng nhập trong cửa sổ được mở và nhấn Enter tại PowerShell. Cả tệp cookie và thư mục phiên đều là dữ liệu nhạy cảm, đã được Git bỏ qua; không gửi chúng cho người khác. Tệp cookie cũ không còn được nạp tự động vì X đã từ chối phiên đó.

Chrome do chương trình mở dùng hồ sơ riêng ở `data/x_browser_profile/`, nên ban đầu không có phiên đăng nhập giống cửa sổ Chrome bạn dùng hằng ngày. Nếu cookie trong tệp bị X từ chối và bạn chạy không có `--headless`, chương trình sẽ chờ bạn đăng nhập ngay trong cửa sổ mới. Đăng nhập xong, quay lại PowerShell và nhấn Enter. Những lần chạy sau sẽ ưu tiên phiên đã lưu trong hồ sơ này; bạn không cần sao chép cookie nữa. Nếu muốn tiếp tục dùng tệp cookie, hãy lấy `auth_token` và `ct0` mới từ **cùng một phiên X đang đăng nhập** và thay trực tiếp trong `data/x_cookies.json`. Không gửi các giá trị đó qua chat.

Nếu X hoặc Google từ chối đăng nhập trong cửa sổ do Playwright mở, hãy đợi giới hạn đăng nhập của X hết, rồi mở chính hồ sơ riêng bằng Chrome thường (không qua Playwright):

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="D:\Web-Crawler-SEG301\data\x_browser_profile" "https://x.com/login"
```

Đăng nhập xong, đóng **toàn bộ cửa sổ Chrome của hồ sơ này** trước khi chạy `python main.py` để chương trình mở lại cùng hồ sơ. Không trỏ chương trình vào hồ sơ Chrome mặc định của bạn.

Nếu `--headless` báo `ERR_HTTP_RESPONSE_CODE_FAILURE`, hãy thử chạy không có `--headless` để xem X đang hiển thị gì. X có thể không cho tải trang ở chế độ chạy ẩn; mã không thể bảo đảm vượt qua hạn chế đó.

Có thể dùng ID bài viết trực tiếp, lặp lại `--post`, hoặc cung cấp `--posts-file` (mỗi dòng một URL/ID):

```powershell
python main.py --post 1234567890123456789 --max-comments 500 --max-scrolls 50 --format jsonl --output data/replies.jsonl
python main.py --posts-file posts.txt --db data/comments.db --output data/x_comments.csv
```

Chế độ trình duyệt chỉ lấy các bài mà giao diện tải và hiển thị trong giới hạn cuộn; **không bảo đảm lấy đủ replies và có thể lẫn bài gợi ý**. Giao diện không cung cấp chắc chắn ID tác giả, reply cha và lượt thích, nên các trường đó lần lượt là `UNKNOWN`, `UNKNOWN` và `0`. Hãy kiểm tra tệp xuất trước khi dùng làm dữ liệu nghiên cứu. Chế độ này phụ thuộc giao diện X và có thể cần sửa khi X thay đổi trang. Hãy bảo đảm việc thu thập phù hợp với điều khoản sử dụng của X.

## Cào qua X API (tùy chọn)

Nếu có quyền dùng X API v2 Search, đặt bearer token trong phiên PowerShell rồi chạy:

```powershell
$env:X_BEARER_TOKEN = "YOUR_X_BEARER_TOKEN"
python main.py --mode api --post "https://x.com/username/status/1234567890123456789"
python main.py --mode api --archive --post 1234567890123456789
```

Mặc định API dùng Recent Search, chỉ tìm replies trong **7 ngày gần nhất**. `--archive` dùng Full-Archive Search nếu tài khoản có quyền. Khi API trả lỗi (gồm HTTP 429), chương trình báo lỗi và dừng.

Mặc định dữ liệu nằm trong `data/comments.db` và `data/x_comments.csv`. Chạy lại cùng bài viết sẽ cập nhật bản ghi theo `(platform, comment_id)`, không tạo bản sao. Tập tin xuất chứa dữ liệu đã lưu của các `post_id` được chọn, kể cả replies lấy từ lần chạy trước.

## Dữ liệu lưu trữ

```sql
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    like_count INTEGER NOT NULL DEFAULT 0 CHECK (like_count >= 0),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (platform, comment_id)
);
```

SQLite dùng `TEXT` cho thời gian ISO 8601 UTC. `id` là ID nội bộ của SQLite. Trong chế độ API, một reply trực tiếp vào bài gốc có `parent_id = "ROOT"`; reply vào reply khác giữ ID của reply cha. Trong chế độ trình duyệt, `parent_id = "UNKNOWN"` vì trang không thể hiện chắc chắn quan hệ này. `post_id` là ID bài gốc được yêu cầu.

CSV và JSONL có cùng thứ tự cột: `id, platform, comment_id, content, author_id, author_name, parent_id, post_id, comment_url, created_at, like_count, collected_at`.
CSV được ghi dưới dạng UTF-8 có BOM để Excel và các ứng dụng Windows nhận đúng tiếng Việt; JSONL dùng UTF-8 thông thường.

## Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Tham khảo API: [Search Posts](https://docs.x.com/x-api/posts/search/introduction), [Search Operators](https://docs.x.com/x-api/posts/search/integrate/operators), [Recent Search](https://docs.x.com/x-api/posts/search-recent-posts).
