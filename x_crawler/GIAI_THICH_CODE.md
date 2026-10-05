# Giải thích chi tiết mã cào bình luận X

Tài liệu này giải thích mã hiện có trong thư mục `x_crawler/` và các file ở thư mục gốc mà crawler X sử dụng. Nội dung mô tả hành vi của code trong repository, không giả định rằng đã chạy cào trực tiếp trên X.

## 1. Crawler X làm gì?

Đầu vào là một hoặc nhiều URL/ID bài viết X. Chương trình tìm các bài xuất hiện bên dưới bài gốc, chuyển chúng thành bản ghi `Comment`, lưu vào SQLite chung, rồi xuất CSV hoặc JSONL.

Có hai cách thu thập:

| Chế độ | Cách lấy dữ liệu | Kích hoạt | Dữ liệu đáng chú ý |
| --- | --- | --- | --- |
| `browser` (mặc định) | Playwright mở Chrome/Chromium, đọc các phần tử HTML đã được trang X hiển thị, rồi cuộn trang | Không cần ghi `--mode` | Không xác định chắc `author_id`, `parent_id`, lượt thích; có thể thiếu reply hoặc lẫn bài gợi ý |
| `api` | Thư viện `requests` gọi X API v2 Search | `--mode api`; cần `X_BEARER_TOKEN` | Có thể lấy quan hệ reply, ID tác giả, lượt thích nếu API trả về |

**“Cào HTML” ở đây nghĩa là đọc DOM sau khi Chrome đã tải và chạy JavaScript của X.** Code không dùng `requests.get()` để tải HTML tĩnh rồi phân tích bằng BeautifulSoup. Trong chế độ API, code nhận JSON từ API thay vì HTML.

## 2. Sơ đồ luồng chạy

```text
python main.py x --post URL
         │
         ▼
main.py (thư mục gốc): chọn crawler X, chuyển đường dẫn database
         │
         ▼
x_crawler/main.py: đọc tham số, kiểm tra và loại URL/ID trùng
         │
         ├── browser ──► x_crawler/platforms/x_browser.py
         │               Playwright → Chrome → DOM đã hiển thị → Comment
         │
         └── api ──────► x_crawler/platforms/x.py
                         X API Search → JSON → Comment
         │
         ▼
database.py: thêm/cập nhật các Comment trong data/comments.db
         │
         ▼
database.py: đọc lại dữ liệu của các bài được chọn
         │
         ▼
x_crawler/export.py: ghi data/x_comments.csv hoặc .jsonl
```

## 3. Vai trò từng file

| File | Vai trò |
| --- | --- |
| `x_crawler/__init__.py` | Đánh dấu thư mục `x_crawler` là package Python; hiện chỉ có docstring. |
| `x_crawler/__main__.py` | Điểm vào cho lệnh `python -m x_crawler`; gọi `x_crawler.main.main()`. |
| `x_crawler/main.py` | Giao diện dòng lệnh riêng của X: đọc tham số, chọn chế độ, gọi crawler, lưu và xuất dữ liệu. |
| `x_crawler/platforms/__init__.py` | Đánh dấu `platforms` là package; hiện chỉ có docstring. |
| `x_crawler/platforms/x_browser.py` | Cào qua trình duyệt: quản lý phiên đăng nhập, mở bài X, đọc DOM và cuộn trang. |
| `x_crawler/platforms/x.py` | Kiểm tra URL/ID X, gọi X API và chuyển JSON API thành `Comment`. |
| `x_crawler/export.py` | Xuất các dòng đã lưu sang CSV hoặc JSONL. |
| `x_crawler/README.md` | Hướng dẫn ngắn cách chạy package X. |

Các file nằm **ngoài** `x_crawler/` nhưng tham gia trực tiếp:

| File | Vai trò đối với X |
| --- | --- |
| `main.py` | Chọn nền tảng khi chạy `python main.py x ...`; hỗ trợ lệnh X cũ `python main.py --post ...`. |
| `models.py` | Định nghĩa kiểu dữ liệu `Comment` dùng chung. |
| `database.py` | Tạo bảng SQLite, thêm/cập nhật và đọc bình luận. |
| `shared_database.py` | Cung cấp đường dẫn database mặc định cho `main.py` gốc và xử lý lệnh `migrate`; luồng cào X thông thường không gọi chức năng migrate. |
| `requirements.txt` | Khai báo `playwright` cho chế độ trình duyệt và `requests` cho chế độ API. |

## 4. `main.py` ở thư mục gốc: chọn nền tảng

Hàm `main(argv)` trong `../main.py` nhận các tham số sau `python main.py`.

1. Nếu tham số đầu không phải tên nền tảng đã biết, hàm coi đó là lệnh X kiểu cũ và gọi thẳng `x_crawler.main.main(argv)`. Ví dụ `python main.py --post 123` vẫn chạy được.
2. Với cú pháp mới, `argparse` đọc `--db` và tên nền tảng. `parse_known_args` giữ các tham số còn lại trong `rest` để crawler riêng xử lý.
3. Nếu nền tảng là `x`, hàm gọi `x_crawler.main.main([*rest, "--db", db_path])`. Như vậy X nhận đường dẫn SQLite chung đã được chuẩn hóa thành đường dẫn tuyệt đối.
4. Các nhánh `reddit`, `youtube`, `tiktok`, `threads` chuyển cho crawler tương ứng. `migrate` dùng để nhập dữ liệu cũ vào database chung, không thực hiện cào X.
5. Cuối file, `raise SystemExit(main())` chuyển mã trả về của hàm thành mã thoát của chương trình: `0` là thành công, `1` là lỗi thu thập do `x_crawler/main.py` trả về.

Ví dụ đường đi của lệnh:

```powershell
python main.py --db data/comments.db x --post https://x.com/user/status/123
```

`main.py` gốc chọn `x`, lấy `--post ...` làm `rest`, rồi chuyển `--db` đã chuẩn hóa sang `x_crawler/main.py`.

## 5. `x_crawler/__main__.py`: cách chạy trực tiếp package

Lệnh sau không đi qua `main.py` gốc:

```powershell
python -m x_crawler --post 123
```

Python chạy `x_crawler/__main__.py`; file này import `main` từ `.main` rồi gọi `raise SystemExit(main())`. Các giá trị mặc định của database và hồ sơ Chrome trong `x_crawler/main.py` vẫn trỏ về thư mục `data/` ở gốc dự án.

## 6. `x_crawler/main.py`: điều phối một lần cào X

### 6.1. Đường dẫn và tham số

`BASE_DIR` là thư mục `x_crawler`; `ROOT_DIR` là thư mục dự án. Từ đó file xác định `DEFAULT_DB = data/comments.db` và `DEFAULT_PROFILE = data/x_browser_profile`.

Các tham số chính:

| Tham số | Ý nghĩa | Mặc định |
| --- | --- | --- |
| `--post URL_OR_ID` | Một bài X; có thể lặp nhiều lần | Không có |
| `--posts-file PATH` | File văn bản chứa mỗi dòng một URL/ID; bỏ dòng trống và dòng bắt đầu bằng `#` | Không có |
| `--mode browser\|api` | Cách thu thập | `browser` |
| `--profile-dir PATH` | Hồ sơ trình duyệt dùng để giữ phiên đăng nhập X | `data/x_browser_profile` |
| `--cookie-file PATH` | File JSON tùy chọn chứa `auth_token` và `ct0` | Không có; không tự nạp cookie file |
| `--browser-channel chrome\|chromium` | Trình duyệt Playwright mở | `chrome` |
| `--headless` | Chạy trình duyệt không hiện cửa sổ | Tắt |
| `--max-scrolls N` | Số vòng cuộn tối đa trên mỗi bài ở chế độ trình duyệt | `30` |
| `--max-comments N` | Số bình luận tối đa lấy trên mỗi bài | `1000` |
| `--archive` | Dùng Full-Archive Search; chỉ hợp lệ với `--mode api` | Tắt |
| `--db PATH` | File SQLite | `data/comments.db` |
| `--output PATH` | File kết quả | `data/x_comments.csv` hoặc `.jsonl` |
| `--format csv\|jsonl` | Định dạng file kết quả | `csv` |

### 6.2. Kiểm tra đầu vào và loại trùng

Sau khi đọc `--post` và `--posts-file`, chương trình báo lỗi nếu không có bài nào, nếu `--max-comments` hoặc `--max-scrolls` nhỏ hơn 1, hoặc nếu dùng `--archive` mà không chọn API.

Mỗi URL/ID được đưa qua `parse_post_id`. Dictionary `post_inputs` dùng ID làm khóa và giữ đầu vào đầu tiên làm giá trị. Do đó hai URL khác nhau trỏ tới cùng một bài chỉ được cào một lần. Với chế độ trình duyệt, giá trị gốc này còn giúp giữ đường dẫn permalink do người dùng đưa vào.

### 6.3. Chọn crawler, lưu và xuất

- Nếu `--mode api`, hàm đọc `X_BEARER_TOKEN` từ biến môi trường và tạo `XCommentsCrawler`.
- Nếu `--mode browser`, hàm tạo `XBrowserCrawler` với hồ sơ, cookie file, chế độ headless và loại trình duyệt đã chọn.
- Vòng lặp gọi `crawler.crawl(...)` cho từng ID bài. Kết quả của mỗi bài được lưu ngay bằng `database.upsert_comments(args.db, comments)`.
- Nếu cào lỗi, hàm in `Collection stopped: ...` ra stderr và trả `1`. Khối `finally` luôn gọi `crawler.close()` nếu crawler đã được tạo.
- Nếu mọi bài được cào thành công, chương trình đọc lại các bình luận X có `post_id` thuộc danh sách đã chọn, rồi gọi `export_comments`.

**File xuất là ảnh chụp dữ liệu đang có trong database cho các bài được chọn.** Nếu các bài ấy đã được cào trước đây, file xuất có thể chứa cả dữ liệu từ những lần chạy trước. Nếu lỗi giữa nhiều bài, các bài đã cào trước lỗi có thể đã được lưu, nhưng bước xuất cuối không chạy.

## 7. `x_crawler/platforms/x_browser.py`: cào DOM đã hiển thị

### 7.1. `VISIBLE_POSTS_JS`

Đây là một đoạn JavaScript được Playwright chạy trong trang. Với từng `article[data-testid="tweet"]`, nó tìm:

- Thẻ `<time>` và liên kết bao quanh: lấy thời gian ISO và URL bài.
- Phần tử `[data-testid="tweetText"]`: lấy nội dung bằng `innerText`.
- Phần tử `[data-testid="User-Name"] span`: lấy tên hiển thị của tác giả.

Kết quả là các dictionary nhỏ có khóa `url`, `created_at`, `content`, `author_name`. Code đọc phần tử HTML đang hiển thị, không lưu toàn bộ HTML trang và không gọi các endpoint nội bộ của X.

### 7.2. Hàm hỗ trợ

- `_visible_post_id(raw)` lấy ID từ `raw["url"]` bằng `parse_post_id`; URL sai trả `None`.
- `browser_post_url(post)` đổi ID số thành `https://x.com/i/web/status/<ID>`. Với URL hợp lệ, nó giữ đường dẫn permalink và bỏ query string.
- `load_cookies(path)` đọc JSON chứa hai chuỗi `auth_token`, `ct0`; thiếu một trong hai sẽ báo lỗi. Hàm tạo cấu trúc cookie cho domain `.x.com` và không in giá trị cookie.
- Khi truyền `--cookie-file` nhưng đường dẫn không tồn tại, hàm khởi tạo hiện tại bỏ qua file đó mà không báo lỗi riêng; nếu chạy headless và không có phiên trong hồ sơ, lần cào sau đó sẽ báo thiếu phiên đăng nhập.
- `SessionRejectedError` đánh dấu tình huống X không giữ lại phiên cookie sau khi điều hướng.

### 7.3. `XBrowserCrawler.__init__`: mở Chrome

Playwright được import tại đây, nên chỉ khi chạy chế độ trình duyệt mới cần mở browser. `launch_persistent_context` dùng `profile_dir`: cookie và trạng thái đăng nhập có thể còn ở lần chạy sau. Nếu hồ sơ chưa có phiên mà người dùng đã chỉ định cookie file hợp lệ, chương trình thêm cookie từ file. Cuối cùng nó chọn trang có sẵn hoặc mở trang mới.

Hai cờ nội bộ cần phân biệt:

- `_session_expected`: chương trình có lý do để chờ một phiên đăng nhập, vì hồ sơ hoặc cookie file có cookie.
- `_ready`: crawler xem phiên đã sẵn sàng để thử mở bài.

Hồ sơ riêng này không tự dùng phiên Chrome thường ngày của người dùng.

### 7.4. `XBrowserCrawler.crawl`: mở bài và cuộn

1. Xác thực URL/ID, `max_comments` và `max_scrolls`; tạo URL cần mở.
2. Nếu chạy headless mà chưa có phiên, báo lỗi vì không thể hoàn tất đăng nhập tương tác.
3. `_open_post` điều hướng đến bài. Nếu X loại phiên đã lưu: headless báo lỗi; chế độ có cửa sổ chuyển sang chờ đăng nhập lại.
4. Khi cần, chương trình chờ người dùng đăng nhập trong cửa sổ Chrome rồi nhấn Enter tại terminal. Nó kiểm tra lại hai cookie trước khi mở lại bài.
5. Chờ ít nhất một thẻ bài viết xuất hiện và xác nhận trong các thẻ đang hiển thị có ID bài gốc được yêu cầu.
6. Trong tối đa `max_scrolls` vòng: đọc tất cả thẻ bài đang hiển thị, chuyển bằng `map_visible_reply`, dùng dictionary theo `comment_id` để loại trùng, rồi cuộn xuống khoảng `0.85` chiều cao cửa sổ và đợi `1200` mili giây.
7. Dừng khi đủ `max_comments` hoặc ba vòng liền không có **bình luận hợp lệ mới** trong dictionary `found`. Trả danh sách `Comment` đã gom.

`_open_post` còn kiểm tra lỗi điều hướng, HTTP từ 400 trở lên, và tình huống cookie có trước khi mở trang nhưng biến mất sau đó. `close()` đóng browser context rồi dừng Playwright.

### 7.5. `map_visible_reply`: từ thẻ DOM sang `Comment`

Hàm bỏ thẻ nếu URL không phải bài X hợp lệ, ID trùng bài gốc, thời gian thiếu/mất múi giờ, hoặc nội dung rỗng. Thời gian được đổi sang ISO 8601 UTC. Username được suy ra từ URL; tên hiển thị lấy từ DOM, nếu thiếu thì dùng username.

Các trường mà giao diện không cho xác định chắc được ghi rõ: `author_id="UNKNOWN"`, `parent_id="UNKNOWN"`, `like_count=0`. `post_id` là ID bài gốc đang được cào, `comment_id` là ID của thẻ vừa đọc, và `collected_at` là thời gian của lượt cào.

**Giới hạn quan trọng:** điều kiện hiện tại chỉ kiểm tra thẻ có ID khác bài gốc, URL/thời gian/nội dung hợp lệ. Nó không kiểm chứng quan hệ reply thật sự với bài gốc. Một bài gợi ý xuất hiện trong DOM cũng có thể được nhận là bình luận.

## 8. `x_crawler/platforms/x.py`: cào bằng X API

### 8.1. `parse_post_id` và `_utc_timestamp`

`parse_post_id` nhận ID gồm 1–19 chữ số hoặc URL `http(s)` thuộc `x.com`, `www.x.com`, `twitter.com`, `www.twitter.com`, `mobile.twitter.com`. Đường dẫn phải có dạng `/<user>/status/<ID>` hoặc `/i/web/status/<ID>`. URL sai domain hoặc sai cấu trúc sẽ gây `ValueError`.

`_utc_timestamp` phân tích thời gian có múi giờ, đổi sang UTC, bỏ phần mili giây và xuất dạng `YYYY-MM-DDTHH:MM:SSZ`. Thời gian không có múi giờ bị từ chối.

### 8.2. `XCommentsCrawler.__init__` và `crawl`

Hàm khởi tạo yêu cầu bearer token, tạo `requests.Session`, gắn header `Authorization: Bearer ...` và đặt timeout mặc định 20 giây.

`crawl(post_id, archive=False, max_comments=1000)` làm các bước:

1. Chọn endpoint `https://api.x.com/2/tweets/search/recent` hoặc `/all` nếu `archive=True`.
2. Gửi truy vấn `conversation_id:<post_id> is:reply -is:retweet`. `max_results` mỗi lần gọi nằm trong khoảng 10–100, còn giới hạn tổng là `max_comments`.
3. Yêu cầu thêm thời gian, conversation ID, chỉ số tương tác, nội dung bài dài, thông tin tác giả và bài được tham chiếu.
4. Xử lý lỗi: HTTP 429 có thông báo riêng; HTTP lỗi khác và trường `errors` trong JSON đều làm dừng.
5. Tạo bảng tra cứu user từ `includes.users`, rồi gọi `map_reply` cho từng bài trong `data`.
6. Dùng dictionary theo `comment_id` để loại trùng. Nếu JSON có `meta.next_token`, gọi trang kế tiếp. Tập `seen_tokens` ngăn lặp vô hạn khi API trả lại token đã dùng.
7. Trả danh sách bình luận. `close()` đóng `requests.Session`.

### 8.3. `map_reply`: từ JSON API sang `Comment`

Hàm chỉ nhận bài có ID hợp lệ, khác ID bài gốc, có `conversation_id` đúng bài gốc, có một tham chiếu kiểu `replied_to` đến ID cha hợp lệ và có thời gian tạo hợp lệ.

`parent_id="ROOT"` nếu reply trực tiếp vào bài gốc; nếu reply vào reply khác thì giữ ID của reply cha. `author_id` lấy từ API hoặc `UNKNOWN`; tên và username được tra từ `includes.users` để tạo URL. Lượt thích được ép sang số nguyên không âm; nếu dữ liệu sai thì dùng `0`. Nội dung ưu tiên `note_post`/`note_tweet` rồi mới đến `text`.

Khác với chế độ trình duyệt, nhánh API có điều kiện kiểm tra `conversation_id` và `replied_to`, nên xác định quan hệ reply rõ hơn. Chế độ `recent` phụ thuộc khoảng thời gian tìm kiếm mà X API cho phép; `--archive` cần quyền API tương ứng.

## 9. `models.py`, `database.py` và `export.py`: dữ liệu sau khi cào

### 9.1. Bản ghi `Comment`

`../models.py` định nghĩa dataclass bất biến `Comment`:

| Trường | Ý nghĩa |
| --- | --- |
| `platform` | Với crawler này luôn là `x`. |
| `comment_id` | ID bài/reply được thu thập trên X. |
| `content` | Nội dung văn bản. |
| `author_id`, `author_name` | ID và tên tác giả; trình duyệt không xác định chắc ID. |
| `parent_id` | `ROOT` nếu API xác định reply trực tiếp, ID reply cha nếu reply lồng nhau, hoặc `UNKNOWN` ở browser. |
| `post_id` | ID bài gốc mà người dùng yêu cầu cào. |
| `comment_url` | URL của bình luận. |
| `created_at` | Thời gian bình luận được tạo, chuẩn hóa UTC. |
| `like_count` | Số lượt thích, hoặc `0` khi browser không lấy được. |
| `collected_at` | Thời gian chương trình thu thập. |

`id` **không nằm trong dataclass**: đó là khóa nội bộ tự tăng do SQLite tạo khi lưu.

### 9.2. Lưu SQLite

`../database.py` tạo bảng `comments` và index `(platform, post_id)`. Ràng buộc `UNIQUE(platform, comment_id)` bảo đảm cùng một bình luận X không tạo nhiều dòng khi cào lại.

`upsert_comments` dùng `INSERT ... ON CONFLICT DO UPDATE`. Nếu một dòng từng được API cung cấp `author_id`, `parent_id` và lượt thích, lần cào browser sau có giá trị `UNKNOWN` sẽ **giữ lại** ID tác giả, ID cha và lượt thích đã biết. Nội dung, tên, URL, thời gian tạo và thời gian thu thập có thể được làm mới. Hàm trả số bản ghi được đưa vào lệnh ghi, không phải số dòng mới được tạo.

`get_comments` chỉ đọc `platform='x'` với các `post_id` được yêu cầu, sắp theo `created_at` rồi `id`. Vì khóa duy nhất là `(platform, comment_id)`, mỗi bình luận X chỉ có một dòng trong bảng chung.

### 9.3. Xuất file

`x_crawler/export.py` định nghĩa thứ tự các cột, tạo thư mục đầu ra và ghi:

- CSV: `utf-8-sig` (UTF-8 có BOM), thuận tiện mở tiếng Việt trong Excel trên Windows.
- JSONL: UTF-8, mỗi dòng là một đối tượng JSON; `ensure_ascii=False` giữ nguyên chữ tiếng Việt.

File xuất có thêm `id` và các trường từ bảng SQLite, vì bước xuất nhận những dòng đã đọc lại từ database.

## 10. Ví dụ theo dõi một lần chạy

```powershell
python main.py x --post "https://x.com/alice/status/123" --max-comments 50 --max-scrolls 20
```

1. `main.py` gốc nhận nền tảng `x` và chuyển lệnh sang `x_crawler.main` cùng đường dẫn `data/comments.db`.
2. `x_crawler.main` lấy `post_id="123"`, chọn `browser` vì không có `--mode api`.
3. `XBrowserCrawler` mở Chrome với hồ sơ `data/x_browser_profile`. Nếu chưa có phiên, chương trình chờ đăng nhập trong cửa sổ Chrome.
4. Playwright mở bài `123`, đọc các thẻ `article[data-testid="tweet"]` trên DOM và cuộn tối đa 20 vòng, dừng sớm nếu đủ 50 mục hoặc không có ID mới sau ba vòng.
5. Mỗi thẻ hợp lệ trở thành một `Comment` có `post_id="123"`; thẻ bài gốc bị bỏ. Các trường không biết chắc được ghi `UNKNOWN` hoặc `0`.
6. `database.upsert_comments` thêm hoặc cập nhật các bình luận vào `data/comments.db`.
7. `database.get_comments` đọc lại dữ liệu X của bài `123`; `export_comments` ghi `data/x_comments.csv`.

Nếu thêm `--mode api`, bước 3–5 được thay bằng `XCommentsCrawler`: dùng bearer token, gọi X API Search và phân trang JSON.

## 11. Cách chạy thường dùng

Trên máy mới, cài các thư viện bằng `python -m pip install -r requirements.txt` và bảo đảm có Google Chrome. Nếu chọn `--browser-channel chromium`, cài Chromium bằng `python -m playwright install chromium`. Lần đầu dùng chế độ trình duyệt, chạy trong terminal tương tác, để cửa sổ Chrome hiện ra, đăng nhập X rồi nhấn Enter tại terminal. Xem thêm `../README.md` để biết cách quản lý hồ sơ và cookie.

```powershell
# Mặc định: Playwright + Chrome, đọc DOM đã hiển thị.
python main.py x --post "https://x.com/user/status/123"

# Nhiều bài từ một file, xuất JSONL.
python main.py x --posts-file posts.txt --format jsonl --output data/x_replies.jsonl

# API: đặt bearer token trong phiên terminal trước khi chạy.
$env:X_BEARER_TOKEN = "YOUR_TOKEN"
python main.py x --mode api --post 123

# Chạy trực tiếp package X.
python -m x_crawler --post 123
```

Để xem đầy đủ tham số, chạy `python main.py x -h`. Không đưa bearer token hoặc nội dung cookie vào repository hay tài liệu chia sẻ.
