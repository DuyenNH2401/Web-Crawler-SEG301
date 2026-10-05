# Giải thích từng file của crawler VOZ

Tài liệu này đi theo đúng cấu trúc thư mục `voz_crawler/`. Crawler dùng `requests` để tải HTML và Beautiful Soup để đọc HTML; dữ liệu được lưu vào SQLite chung của dự án và một file CSV.

```text
voz_crawler/
├── __init__.py
├── __main__.py
├── config.py
├── models.py
├── network.py
├── parser.py
├── crawler.py
├── database.py
├── main.py
├── README.md
└── GIAI_THICH_CODE.md
```

## 1. `config.py` — Cấu hình mặc định

File này tập hợp những giá trị có thể cần thay đổi mà không phải tìm trong logic cào:

| Tên | Ý nghĩa |
| --- | --- |
| `FORUM_URL` | Trang bắt đầu: box Chuyện trò linh tinh™ của VOZ |
| `DEFAULT_DB` | Đường dẫn SQLite chung, lấy từ `shared_database.py` ở thư mục gốc |
| `DEFAULT_CSV` | File CSV mặc định: `data/voz_comments.csv` |
| `DEFAULT_FORUM_PAGES` | Mặc định đọc 1 trang danh sách chủ đề |
| `DEFAULT_MAX_THREADS` | Mặc định đọc tối đa 5 chủ đề |
| `DEFAULT_THREAD_PAGES` | Mặc định đọc tối đa 2 trang trong mỗi chủ đề |
| `DEFAULT_DELAY` | Nghỉ 1,5 giây giữa các lần tải trang |
| `REQUEST_TIMEOUT` | Dừng yêu cầu HTTP nếu quá 20 giây |
| `USER_AGENT` | Giá trị nhận diện chương trình khi gửi yêu cầu HTTP |
| `CSV_FIELDS` | Tên và thứ tự các cột khi xuất CSV |

Các giá trị `DEFAULT_*` được `main.py` dùng làm giá trị ban đầu cho tham số dòng lệnh. Người chạy có thể ghi đè chúng bằng `--max-threads`, `--thread-pages`, v.v.

## 2. `models.py` — Mô tả một chủ đề

`Thread` là một `dataclass` chứa ba thông tin: `thread_id`, `title` và `url`. Ví dụ, URL `https://voz.vn/t/ten-chu-de.123/` có `thread_id` là `123`.

`parser.py` tạo `Thread` từ trang danh sách; `crawler.py` dùng đối tượng đó để mở từng chủ đề; `database.py` dùng `title` khi xuất CSV. `frozen=True` có nghĩa là thông tin của `Thread` không bị thay đổi sau khi tạo.

Đối với bình luận, crawler dùng lớp `Comment` có sẵn trong `../models.py` của dự án để tương thích với bảng SQLite chung.

## 3. `network.py` — Tải trang

- `create_session()` tạo một `requests.Session` và gắn `USER_AGENT`. Session giúp tái sử dụng kết nối khi tải nhiều trang.
- `get_page(session, url)` tải một URL, chờ tối đa `REQUEST_TIMEOUT`, báo lỗi nếu HTTP thất bại (`raise_for_status()`), rồi trả về đối tượng `BeautifulSoup`.

File này chỉ lo việc tải và chuyển HTML thành đối tượng có thể tìm kiếm. Nó không chọn chủ đề hay đọc bình luận; phần đó nằm ở `parser.py`.

## 4. `parser.py` — Đọc HTML

Đây là file chứa các bộ chọn HTML của VOZ. Nếu giao diện VOZ thay đổi, thường cần kiểm tra file này trước.

### `next_page(soup, current_url)`

Tìm liên kết `a.pageNav-jump--next` (nút **Sau**). Hàm dùng `urljoin()` để đổi URL tương đối như `/t/.../page-2` thành URL đầy đủ. Nếu không có trang sau, hàm trả `None`.

### `threads_on_page(soup)`

Tìm từng `.structItem--thread` trên trang danh sách, lấy liên kết trong `.structItem-title a[data-tp-primary]`, rồi tách ID ở cuối URL bằng `THREAD_ID`. Hàm chỉ nhận URL thuộc `voz.vn` và trả về danh sách `Thread`.

### `comments_on_page(soup, thread_id, page_url, skip_original)`

Tìm các thẻ `article.message--post[data-content]`. Ở trang đầu, `skip_original=True` để bỏ bài đăng đầu tiên vì đó là bài gốc của chủ đề. Các bài sau được xem là bình luận.

Với mỗi bài, hàm:

1. Lấy ID từ `data-content`, ví dụ `post-456` → `comment_id="456"`.
2. Lấy nội dung từ `.message-body .bbWrapper`. Các khối trích dẫn, `script` và `style` được bỏ khỏi nội dung. Bài không còn chữ sẽ bị bỏ qua.
3. Lấy tên và ID tác giả từ `.message-name a` nếu có.
4. Lấy thời gian từ `.message-attribution-main time[datetime]` và đổi sang UTC.
5. Tạo một `Comment` với `platform="voz"`, `post_id` là ID chủ đề và `comment_url` trỏ tới đúng trang chứa bình luận cùng `#post-ID`.

Nếu không thấy bài đăng nào, hàm báo lỗi vì trang có thể đã đổi cấu trúc hoặc không tải đúng nội dung. VOZ hiển thị thảo luận dạng phẳng nên crawler ghi `parent_id="UNKNOWN"`; crawler cơ bản này không đọc lượt thích nên `like_count=0`.

## 5. `crawler.py` — Điều phối toàn bộ quá trình

Hàm `crawl(forum_pages, max_threads, thread_pages, delay, db_path, csv_path)` làm việc theo thứ tự:

1. Mở session bằng `network.create_session()`.
2. Tải tối đa `forum_pages` trang danh sách từ `FORUM_URL`; dùng `parser.threads_on_page()` để lấy tối đa `max_threads` chủ đề. `seen_threads` tránh lặp chủ đề xuất hiện trên nhiều trang.
3. Với mỗi chủ đề, tải tối đa `thread_pages` trang. Dùng `parser.comments_on_page()` để lấy bình luận; `seen_comments` tránh lặp ID trong cùng một lần chạy.
4. Gọi `database.save_comments()` sau mỗi trang bình luận để lưu vào SQLite. Có `time.sleep(delay)` giữa các lần tải.
5. Sau khi đọc xong, gọi `database.write_csv()` để xuất các bình luận của lần chạy hiện tại và trả về số bình luận.

Ví dụ `--max-threads 5 --thread-pages 2` nghĩa là tối đa 5 chủ đề và tối đa 2 trang bình luận cho mỗi chủ đề; đó là **giới hạn tối đa**, không phải số trang chắc chắn sẽ có.

## 6. `database.py` — Lưu dữ liệu

- `save_comments(db_path, comments)` gọi `upsert_comments()` trong `../database.py`. Bảng chung dùng khóa `(platform, comment_id)`, nên chạy lại sẽ cập nhật bản ghi cùng ID thay vì thêm bản sao.
- `write_csv(csv_path, rows)` tạo thư mục đích nếu cần, ghi tiêu đề cột theo `CSV_FIELDS`, rồi ghi từng cặp `(Thread, Comment)` vào CSV. File dùng `utf-8-sig` để Excel hiển thị tiếng Việt thuận tiện. File CSV được ghi lại từ đầu trong mỗi lần chạy.

SQLite chứa nhiều trường hơn CSV, gồm `author_id`, `parent_id`, `like_count` và `collected_at`. CSV tập trung vào những trường dễ xem: chủ đề, ID bình luận, tác giả, nội dung, thời gian và URL.

## 7. `main.py` — Lệnh và xử lý lỗi

Hàm `main(argv)` tạo các tham số `--forum-pages`, `--max-threads`, `--thread-pages`, `--delay`, `--db` và `--output`. Nó kiểm tra số trang/số chủ đề phải lớn hơn 0 và thời gian nghỉ không âm. Sau đó nó gọi `crawler.crawl()`.

Nếu HTTP thất bại, không tìm thấy nội dung, hoặc không ghi được file, hàm in thông báo lỗi và kết thúc với mã lỗi. File này cũng đặt mã hóa UTF-8 cho đầu ra để thông báo tiếng Việt hiển thị đúng trên Windows.

## 8. `__main__.py` và `__init__.py` — Điểm vào package

- `__main__.py` gọi `main()` để có thể chạy `python -m voz_crawler`.
- `__init__.py` đánh dấu `voz_crawler` là một package Python; file này không thực hiện việc cào.

## 9. Các file liên quan ở thư mục gốc

- `../main.py` nhận lệnh `python main.py voz`, rồi chuyển tham số cho `voz_crawler/main.py`. Tùy chọn `--db` chung của dự án cũng được chuyển theo.
- `../models.py` định nghĩa `Comment` dùng chung cho các nền tảng.
- `../database.py` tạo bảng `comments` và thêm/cập nhật bình luận theo `(platform, comment_id)`.
- `../shared_database.py` cung cấp đường dẫn SQLite mặc định `data/comments.db`.

## 10. `README.md` và `GIAI_THICH_CODE.md` — Tài liệu

- `README.md` hướng dẫn cài thư viện, chạy lệnh và tìm file kết quả.
- `GIAI_THICH_CODE.md` (file này) giải thích vai trò và cách hoạt động của từng file; nó không được chương trình Python thực thi.

## Ví dụ chạy và kết quả

Từ thư mục gốc dự án:

```powershell
python -m pip install -r requirements.txt
python main.py voz --max-threads 2 --thread-pages 2
```

Kết quả nằm ở `data/comments.db` và `data/voz_comments.csv`. Xem `python main.py voz -h` để biết các tham số khác.
