# Reddit crawler bằng cookie

Python 3.10+, chỉ dùng thư viện chuẩn. Lấy comment và reply từ các bài mới trong
subreddit bằng cookie đăng nhập của trình duyệt, rồi lưu vào SQLite.
Không cần cài thư viện, API key, OAuth hoặc file `.env`.

## 1. Chuẩn bị cookie

1. Đăng nhập Reddit và mở `https://www.reddit.com/r/python/`.
2. Nhấn F12 → **Network**, tải lại trang và chọn request tới **www.reddit.com**.
3. Mở **Headers → Request Headers**, sao chép giá trị **Cookie**.
   Lấy một dòng dạng `reddit_session=...; ten_khac=...`, không lấy `Set-Cookie`.
4. Tạo file local bằng trình soạn thảo:

```bash
mkdir -p .secrets
chmod 700 .secrets
nano .secrets/reddit-cookie.txt
```

Dán cookie vào file, lưu rồi đặt quyền đọc:

```bash
chmod 600 .secrets/reddit-cookie.txt
```

Cookie là thông tin đăng nhập: không gửi qua chat hoặc commit vào Git.
`.secrets/` đã nằm trong `.gitignore`. Crawler không sửa file cookie và không
in giá trị cookie vào log; cookie chỉ gửi qua HTTPS tới `www.reddit.com`.

## 2. Crawl

```bash
python3 reddit_crawler.py crawl \
  --cookies-file .secrets/reddit-cookie.txt \
  --subreddit python \
  --max-comments 100 \
  --max-posts 10
```

Thay `python` bằng subreddit cần lấy, `100` bằng số comment tối đa muốn lưu.
Database mặc định là `data/reddit.sqlite3`; dùng `--db` để chọn file khác.

| Tham số | Ý nghĩa |
| --- | --- |
| `--cookies-file` | Bắt buộc; file chứa Cookie request header |
| `--subreddit` | Bắt buộc; tên như `python` hoặc `r/python` |
| `--max-comments` | Bắt buộc; giới hạn comment hợp lệ, duy nhất trên toàn lần chạy |
| `--max-posts` | Số bài mới tối đa, mặc định 100 |
| `--request-delay` | Khoảng cách tối thiểu giữa request, mặc định 2 giây |
| `--timeout` | Timeout thao tác socket, mặc định 30 giây |
| `--user-agent` | Mô tả crawler; có thể thêm tên tài khoản liên hệ |
| `--db` | File SQLite, mặc định `data/reddit.sqlite3` |
| `--dry-run` | Đọc Reddit và đếm dự kiến, không tạo hoặc sửa database |

Thử kết nối với một bài trước khi lưu:

```bash
python3 reddit_crawler.py crawl \
  --cookies-file .secrets/reddit-cookie.txt \
  --subreddit python --max-comments 1 --max-posts 1 \
  --timeout 10 --dry-run
```

Log và tiến trình nằm ở stderr; kết quả JSON cuối nằm ở stdout.
Muốn vừa xem vừa lưu log, thêm `2>&1 | tee crawl.log` vào cuối lệnh.
`Đã đọc file cookie` chỉ xác nhận đọc file, chưa xác nhận đăng nhập hay lấy dữ liệu.

## 3. Xem dữ liệu

```bash
python3 reddit_crawler.py show --limit 20
python3 reddit_crawler.py stats
```

Thêm `--db duong-dan.sqlite3` nếu đã crawl vào file khác. Hai lệnh chỉ đọc.
`show` in mỗi comment một dòng; `stats` trả tổng số comment và số lượng theo subreddit.

## Hành vi và giới hạn

- Gửi HTTP tới JSON của website Reddit (`/new.json`, `/comments/<id>.json`) với
  cookie local. Chỉ có một cách crawl; không còn chế độ public hoặc adapter PRAW.
- Lấy cả reply có trong response ban đầu; tham số request giới hạn tối đa 500
  comment mỗi bài và không mở thêm nhánh `more`. Vì vậy có thể lấy ít hơn `--max-comments`.
  Kết quả `unexpanded_branches` báo số nhánh chưa mở.
- ID trùng được cập nhật, không tạo bản ghi mới. `saved` là số comment duy nhất
  được lưu/cập nhật trong lần chạy; `created` và `updated` phân biệt hai trường hợp.
- Bỏ qua `[deleted]`/`[removed]`; nếu gặp lại ID đã lưu với nội dung này thì xoá
  bản ghi đó. Không có sync nền hoặc tự xoá dữ liệu sau 48 giờ.
- HTTP 401/403 dừng ngay; cookie có thể hết hạn và không đảm bảo tránh được 403.
  HTTP 429/5xx thử lại tối đa hai lần, tôn trọng `Retry-After`.
  DNS, timeout hoặc JSON không hợp lệ báo lỗi; không tạo dữ liệu thay thế.
- Ctrl+C hoặc lỗi giữ các bản ghi đã lưu trước đó. Chạy lại để tiếp tục cập nhật.
- Giữ schema SQLite hiện có và tự chuyển đổi schema cũ khi crawl ghi dữ liệu.
  Bảng `comments` có 11 cột: `platform`, `comment_id`, `content`, `author_id`,
  `author_name`, `parent_id`, `post_id`, `comment_url`, `created_at`, `like_count`,
  `collected_at`. Trường thiếu lưu `NULL`; `like_count` là `score` Reddit trả về,
  có thể âm. `collected_at` giữ thời điểm lưu lần đầu.

## Code và kiểm thử

Luồng chính: `main.py` → `RedditClient` → `crawl()` → `Store.save()`.

```text
reddit_crawler.py       Điểm chạy CLI
reddit_app/
  main.py, parser.py    Lệnh crawl/show/stats và tham số
  clients.py           Cookie, HTTP, phân trang, duyệt reply
  crawler.py           Giới hạn, chống trùng, điều phối lưu
  models.py            Chuẩn hoá comment JSON
  database.py          SQLite, cập nhật, migration, xem và thống kê
  network.py           Retry và thông báo lỗi mạng
  progress.py          Log tiến trình khi đang chờ HTTP
  config.py            Giá trị mặc định; không chứa secrets
```

```bash
python3 -m unittest discover -s tests -v
```

Tests dùng cookie, HTTP response và database giả lập, chạy offline.
Kết nối Reddit bằng cookie thật chưa được xác minh trong môi trường này.
