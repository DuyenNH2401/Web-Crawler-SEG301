# Reddit comments → SQLite

CLI Python 3.10+ để lấy comment từ các bài mới trong một subreddit, hoặc nhập
JSONL vào SQLite. Số lượng comment được đặt bằng `--max-comments`, không hardcode.
Giữ cả reply và `parent_id`; dùng ID comment để tránh trùng khi chạy lại.

## Cấu trúc code và thứ tự đọc

`reddit_crawler.py` là điểm khởi chạy, chỉ gọi `main()` trong package
`reddit_app`. Các lệnh `python3 reddit_crawler.py ...` vẫn sử dụng như trước.
Giữ nguyên cả thư mục `reddit_app` khi sao chép chương trình sang máy khác.

```text
reddit_crawler.py
reddit_app/
    __init__.py
    main.py
    parser.py
    config.py
    models.py
    database.py
    clients.py
    crawler.py
    progress.py
    network.py
tests/
examples/
```

| File | Nhiệm vụ và hàm/class chính |
| --- | --- |
| `reddit_crawler.py` | Gọi `main()` và trả exit code cho terminal |
| `reddit_app/main.py` | Đọc args, chọn client, mở database, điều phối lệnh và xử lý lỗi |
| `reddit_app/parser.py` | `parser()`, `positive_int()`, `nonnegative_int()`, `positive_float()` |
| `reddit_app/config.py` | Giá trị mặc định, giới hạn request, logger và dấu hiệu comment đã xóa; không chứa secrets |
| `reddit_app/models.py` | `Comment.from_value()` chuẩn hóa dữ liệu; `subreddit_name()` kiểm tra subreddit |
| `reddit_app/database.py` | `Store` quản lý SQLite; `show_comments()` và `database_stats()` chỉ đọc dữ liệu |
| `reddit_app/clients.py` | `PublicReddit`, `PublicForest`; đọc cookie local và tạo client JSON/PRAW |
| `reddit_app/crawler.py` | `crawl()`, `consume()`, `counters()`, `sync()`, `import_jsonl()` |
| `reddit_app/progress.py` | `CrawlProgress` cập nhật trạng thái bằng thread phụ |
| `reddit_app/network.py` | `request_with_backoff()`, `network_error_message()`, `diagnose_network()` |

Để đọc hiểu hoặc trình bày với giáo viên, đọc theo thứ tự:

1. `reddit_crawler.py` → `parser.py` → `main.py`: lệnh terminal được điều phối ra sao.
2. `models.py` → `database.py`: dữ liệu được chuẩn hóa và lưu theo 11 trường như thế nào.
3. `crawler.py` → `clients.py`: cách lấy bài, duyệt cây comment, chống trùng và gọi HTTP.
4. `network.py` → `progress.py` → `config.py`: retry, chẩn đoán, tiến trình và cấu hình mặc định.

Luồng thu thập là `main()` → tạo client/`Store` → `crawl()` →
`Comment.from_value()` → `consume()` → `Store.save()`. Các module nghiệp vụ
không import ngược `main.py`, giúp tránh phụ thuộc vòng.

Các test import trực tiếp từ module chứa chức năng cần kiểm tra. Khi dùng code
trong Python, có thể import `from reddit_app.database import Store` hoặc
`from reddit_app.crawler import crawl`. File `reddit_crawler.py` dành cho CLI.

## Schema SQLite

Bảng `comments` có đúng 11 trường sau. Trường không lấy được lưu SQL `NULL`
(Python `None`, JSON `null`), không thay bằng chuỗi `"None"` hay số 0.

| Trường | Cách lấy / định dạng |
| --- | --- |
| `platform` | Luôn là `reddit` |
| `comment_id` | ID comment, ví dụ `abcxyz`; bắt buộc để chống trùng |
| `content` | Nội dung Markdown từ `body`, hoặc NULL |
| `author_id` | ID từ `author_fullname` nếu có; bỏ tiền tố `t2_`, hoặc NULL |
| `author_name` | Tên tài khoản từ `author.name`, hoặc NULL |
| `parent_id` | `t3_<post_id>` cho comment gốc; `t1_<comment_id>` cho reply, hoặc NULL |
| `post_id` | Giữ tiền tố `t3_`, ví dụ `t3_xxx`, hoặc NULL |
| `comment_url` | URL đầy đủ từ permalink, hoặc NULL |
| `created_at` | Unix timestamp UTC tính bằng giây từ `created_utc`, hoặc NULL |
| `like_count` | Giá trị `score` Reddit trả về, hoặc NULL; có thể âm |
| `collected_at` | Unix timestamp UTC lúc tool lưu lần đầu, tự sinh |

`like_count` dùng điểm `score`, không đảm bảo là số lượt like tuyệt đối; tool
không tự suy ra tổng lượt upvote. Xem các thuộc tính nguồn trong
[tài liệu PRAW](https://praw.readthedocs.io/en/stable/code_overview/models/comment.html).
Không gọi thêm API lấy profile để điền `author_id`; thiếu ID thì để NULL.
Nếu API báo tài khoản tác giả đã xoá (`author=None`), sync xoá tên/ID tác giả
đã lưu nhưng giữ nội dung còn tồn tại.

Subreddit được lưu riêng trong bảng nội bộ `comment_metadata` để lọc và thống
kê, giữ bảng `comments` đúng format trên. Khoá chính là `(platform, comment_id)`.
Khi mở database theo schema cũ của tool, các lệnh ghi tự chuyển đổi trong một
transaction, giữ nội dung và `collected_at`; author/URL cũ chưa có để NULL.
`stats` và `--dry-run` không thay đổi file database cũ.

## Bạn đang làm nghiên cứu và chưa có API

API là giao diện để chương trình gửi yêu cầu và nhận dữ liệu có cấu trúc từ
Reddit. Có tài khoản Reddit chưa đồng nghĩa với có quyền truy cập API.

Theo [hướng dẫn truy cập của Reddit](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data),
nghiên cứu dùng chương trình **Reddit for Researchers (RFR)**. RFR cấp quyền qua
**BigQuery Analytics Hub**, không phải credentials PRAW.

1. Đọc [chương trình RFR](https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program).
2. [Gửi đơn](https://support.reddithelp.com/hc/en-us/requests/new?tf_42139884615700=api_request_type_researcher_clone&ticket_form_id=14868593862164),
   chọn vai trò researcher. Chuẩn bị mục đích nghiên cứu, tên subreddit, nhu cầu
   dữ liệu, email trường, người hướng dẫn/bảo trợ và hồ sơ đánh giá đạo đức hoặc
   miễn đánh giá theo yêu cầu của chương trình.
3. Sau khi được duyệt, làm theo hướng dẫn BigQuery của Reddit. Chỉ xuất/lưu
   offline khi được phép và cần cho nghiên cứu. Nếu cần SQLite, ánh xạ kết quả
   được phép xuất sang định dạng JSONL bên dưới rồi dùng lệnh `import`.

Chương trình có điều kiện về cơ sở nghiên cứu và bảo trợ; một bài tập cá nhân
không tự động đủ điều kiện. Theo tài liệu hiện tại, dữ liệu RFR có độ trễ sáu
tháng và cập nhật hàng tháng. CLI này chưa kết nối trực tiếp BigQuery hay tự
ánh xạ schema RFR; hướng dẫn schema được cung cấp khi bạn được duyệt.

## Thử ngay với dữ liệu giả lập (không cần cài thư viện/API)

`examples/comments.jsonl` chứa ba comment tự tạo, không phải comment thật.

```bash
python3 reddit_crawler.py import --input examples/comments.jsonl --subreddit python --max-comments 2 --db data/demo.sqlite3
python3 reddit_crawler.py stats --db data/demo.sqlite3
```

Chạy lại lệnh import sẽ cập nhật hai bản ghi thay vì thêm bản ghi trùng.
Thay số `2` bằng số bạn muốn. Muốn xem dự kiến mà không ghi database:

```bash
python3 reddit_crawler.py import --input examples/comments.jsonl --subreddit python --max-comments 10 --db data/demo.sqlite3 --dry-run
```

## Thử đọc JSON công khai, không cấu hình OAuth/cookie

Chế độ `crawl-public` dùng thư viện chuẩn Python và gửi HTTP tới endpoint JSON
công khai của Reddit. Không cần PRAW, `.env`, API key hoặc cookie để khởi chạy
chế độ này; việc endpoint có trả dữ liệu hay không phụ thuộc khả năng truy cập.
Đây vẫn là truy cập dữ liệu Reddit, không đồng nghĩa được cấp quyền thu thập.
Theo [quy định Reddit](https://support.reddithelp.com/hc/en-us/articles/360043512931-Don-t-break-the-site),
scraping cần được cho phép. Với nghiên cứu, xem hướng dẫn RFR ở trên.

```bash
python3 reddit_crawler.py crawl-public --subreddit python --max-comments 100 --max-posts 10 --db data/reddit.sqlite3
python3 reddit_crawler.py stats --db data/reddit.sqlite3
```

Seed hiện là tên subreddit: `https://www.reddit.com/r/python/` tương ứng
`--subreddit python`. Chưa hỗ trợ URL từng bài hoặc file danh sách seed.

- `--request-delay`: khoảng cách tối thiểu giữa request, mặc định 2 giây.
- `--timeout`: timeout mỗi request, mặc định 30 giây.
- `--user-agent`: mô tả crawler trung thực; mặc định `linux:seg301-public-comments:v0.1.0`.
  Nếu có tài khoản liên hệ, dùng dạng `linux:seg301-public-comments:v0.1.0 (by /u/ten_cua_ban)`.
- `--dry-run`: đọc nguồn và báo số dự kiến, không tạo/thay đổi database.

Nếu Reddit trả 401/403 thì lệnh dừng. HTTP 429/5xx thử lại tối đa hai lần theo
`Retry-After`/backoff, sau đó báo lỗi. Lỗi mạng/DNS cũng báo lỗi, không ghi dữ liệu
giả để thay thế. Các comment đã commit trước lỗi vẫn còn và có thể cập nhật khi
chạy lại. Với chế độ public, `sync` qua API vẫn cần quyền/credentials riêng.

Chỉ lấy comment và reply có trong JSON ban đầu (tối đa 500 comment tải về mỗi
bài), không mở các nhánh `more`. Vì vậy có thể lấy ít hơn `--max-comments`.
`unexpanded_branches` báo số nhánh chưa mở; chế độ này không đảm bảo đầy đủ lịch
sử hay đại diện toàn subreddit. Đây là giới hạn tải response, không hardcode
số comment cần lưu: tổng cần lưu vẫn do `--max-comments` quyết định.

Kết nối live chưa được xác minh trong môi trường phát triển vì lỗi DNS.

Nếu thấy `không kết nối được Reddit`, bản mới phân loại lỗi gốc và mã lỗi hệ
thống: `gaierror` là DNS, `TimeoutError` là timeout, `SSLCertVerificationError`
là xác minh chứng chỉ HTTPS, `ConnectionRefusedError` là kết nối TCP bị từ chối.
Các lỗi này xảy ra trước khi nhận được HTTP response thành công và khác với
việc Reddit trả HTTP 403. Không dùng kết quả DNS trong môi trường phát triển
để kết luận máy cá nhân cũng lỗi DNS.

Để kiểm tra trên chính terminal đang chạy crawler:

```bash
python3 reddit_crawler.py crawl-public --subreddit python --max-comments 1 --max-posts 1 --timeout 10 --dry-run
```

Với lỗi DNS, kiểm tra phân giải tên bằng cùng interpreter:

```bash
python3 reddit_crawler.py diagnose
```

Lệnh `diagnose` chỉ kiểm tra phân giải tên Reddit, PyPI (để so sánh) và hostname
proxy HTTPS đang được dùng nếu có; không sửa mạng, không gửi credentials và
không đọc/ghi database. Giá trị `assessment` giúp phân biệt:

- `proxy_dns_failure`: hostname proxy được cấu hình không phân giải được;
  kiểm tra lại cấu hình proxy/VPN của terminal.
- `invalid_proxy_configuration`: URL/cổng proxy không hợp lệ.
- `general_dns_failure`: cả Reddit và PyPI đều lỗi khi không dùng proxy;
  kiểm tra resolver/kết nối của máy.
- `reddit_dns_failure`: Reddit lỗi nhưng hostname so sánh hoạt động; kiểm tra
  phân giải tên Reddit và kết quả ở trình duyệt trên cùng máy.
- `dns_ok` / `proxy_dns_ok`: tên cần phân giải đã hoạt động; kiểm tra bước
  HTTPS tiếp theo. Proxy có thể phân giải hostname Reddit từ xa.

Python tự đọc cấu hình proxy từ môi trường và có thể từ cấu hình hệ thống;
`diagnose` chỉ hiển thị hostname, không in username/password hay toàn bộ URL
proxy. Trên Ubuntu có thể xem resolver hiện tại bằng `resolvectl status` nếu
máy dùng systemd-resolved; không thay đổi DNS trước khi biết hostname nào lỗi.

Nếu DNS thành công nhưng crawler vẫn lỗi, dùng loại lỗi mới trong log để kiểm
tra timeout/TLS/proxy. Log không in giá trị proxy hoặc chuỗi lỗi có thể chứa
credentials. Không tắt xác minh chứng chỉ HTTPS để xử lý lỗi TLS.

## Dùng phiên đăng nhập từ trình duyệt

`crawl-session` đọc cookie từ file local và gửi tới `https://www.reddit.com`.
Chế độ này không cần cài PRAW hoặc cấu hình API key. Cookie là thông tin đăng
nhập: giữ trên máy bạn, không gửi qua chat và không đưa giá trị vào lệnh terminal.

Lấy cookie từ phiên Reddit của chính bạn:

1. Đăng nhập Reddit, mở `https://www.reddit.com/r/python/`.
2. Nhấn F12, chọn **Network**, rồi tải lại trang.
3. Chọn request gửi tới **www.reddit.com**, mở **Headers → Request Headers**.
4. Sao chép giá trị **Cookie** (một dòng dạng `ten=gia_tri; ten_khac=gia_tri`).
   Không lấy `Set-Cookie` trong Response Headers. File cũng chấp nhận tiền tố `Cookie:`.

Tạo file riêng và mở bằng trình soạn thảo:

```bash
mkdir -p .secrets
chmod 700 .secrets
nano .secrets/reddit-cookie.txt
```

Dán dòng cookie vào file; với nano, nhấn Ctrl+O, Enter để lưu, rồi Ctrl+X để thoát.
Sau đó chạy:

```bash
chmod 600 .secrets/reddit-cookie.txt
python3 reddit_crawler.py crawl-session \
  --cookies-file .secrets/reddit-cookie.txt \
  --subreddit python --max-comments 100 --max-posts 10 \
  --db data/reddit.sqlite3
python3 reddit_crawler.py stats --db data/reddit.sqlite3
```

Đổi `python` thành subreddit cần lấy và `100` thành số comment bạn muốn lưu.
Giới hạn comment/reply, thời gian chờ, retry và `--dry-run` giống `crawl-public`.
File cookie không bị sửa; `.secrets/` được bỏ qua trong Git và giá trị cookie
không được ghi vào log hoặc database. Cookie chỉ gửi qua HTTPS tới đúng host
`www.reddit.com`, kể cả khi request có redirect.

Phiên đăng nhập có thể hết hạn; lấy lại cookie từ trình duyệt nếu cần. Cookie
không đảm bảo hết lỗi 403 và không thay thế quyền thu thập dữ liệu nghiên cứu.
Nếu Reddit trả 401/403, lệnh dừng. Chưa xác minh kết nối bằng phiên thật trong
môi trường phát triển; tests dùng cookie và response giả lập.

Nếu chỉ thấy `local cookie file loaded`, đó là xác nhận đọc file, chưa xác nhận
đăng nhập thành công hoặc đã lưu comment. Bản hiện tại ghi `request start`
trước khi chờ HTTP response. `^C` nghĩa là bạn đã nhấn Ctrl+C để dừng lệnh.
Thử một bài, timeout ngắn và không ghi database để kiểm tra kết nối:

```bash
python3 reddit_crawler.py crawl-session \
  --cookies-file .secrets/reddit-cookie.txt \
  --subreddit python --max-comments 1 --max-posts 1 \
  --timeout 10 --dry-run
```

Chờ lệnh trả kết quả/lỗi; chỉ chia sẻ log, không chia sẻ cookie. Giá trị timeout
áp dụng cho thao tác socket, không phải giới hạn tổng thời gian của toàn bộ lần
chạy hoặc phân giải DNS. `stats` kiểm tra số bản ghi đang có trong database,
nhưng không xác định riêng số comment của lần chạy bị ngắt.

## Tiến trình và lưu log

Các lệnh `crawl`, `crawl-public`, `crawl-session` tự hiển thị thanh tiến trình
trong log; không cần cài thêm thư viện hoặc bật flag. Ví dụ:

```text
INFO run=... [####----------------] Đang cào 12/50 comment | bài=2 | elapsed=00:00:15 | Lưu vào SQLite
INFO run=... [####----------------] Đang cào 12/50 comment | bài=2 | elapsed=00:00:20 | Đang lấy JSON /r/python/comments/p3.json
```

`12/50` là số comment hợp lệ, duy nhất đã lưu/cập nhật trong lần chạy so với
giới hạn `--max-comments`; comment trùng hoặc đã xoá không làm tăng tiến trình.
Mỗi comment được lưu có một dòng cập nhật. Khi chờ, log trạng thái tiếp tục
xuất hiện mỗi 5 giây và thời gian `elapsed` tăng. Điều này cho biết chương trình
đang hoạt động, không xác nhận Reddit đã trả dữ liệu. Có thể hoàn tất với ít hơn
50 comment nếu hết bài/nhánh JSON trong giới hạn. Dry-run ghi rõ `dry-run` và
đếm comment dự kiến, không ghi database.

Vừa xem vừa lưu toàn bộ log và kết quả cuối vào `crawl.log`:

```bash
python3 reddit_crawler.py crawl-session \
  --cookies-file .secrets/reddit-cookie.txt \
  --subreddit python --max-comments 50 --max-posts 10 \
  --timeout 10 --db data/reddit.sqlite3 2>&1 | tee crawl.log
```

Không chuyển hướng thì log/tiến trình nằm ở stderr, JSON kết quả cuối nằm ở
stdout. Log không chứa cookie hoặc nội dung comment. Worker hiển thị trạng thái
được dừng khi hoàn tất, có lỗi hoặc Ctrl+C; không làm thêm request.

## Lấy từ Data API khi có quyền phù hợp

`crawl` và `sync` là adapter cho Reddit Data API qua PRAW. Chỉ dùng cho mục
đích được Reddit phê duyệt; có client ID/secret không thay thế phê duyệt. Adapter
này không phải cách kết nối chương trình nghiên cứu RFR.

Cài trong virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Nếu Debian/Ubuntu báo thiếu `ensurepip`, cài gói `python3-venv` tương ứng phiên
bản Python của máy rồi tạo lại virtualenv. Chế độ import/tests dùng thư viện
chuẩn nên vẫn chạy mà không có PRAW.

Tạo file cấu hình local:

```bash
cp .env.example .env
```

Điền credentials được cấp vào `.env`, sau đó nạp bằng shell:

```bash
set -a
source .env
set +a
```

Chương trình đọc biến môi trường, không tự nạp `.env`. File `.env` và database
đã được thêm vào `.gitignore`. Không cần mật khẩu tài khoản Reddit.

Ví dụ tối đa 1.000 comment trong 50 bài mới của `r/python`:

```bash
python3 reddit_crawler.py crawl --subreddit python --max-comments 1000 --max-posts 50 --more-limit 8 --db data/reddit.sqlite3
```

| Argument | Ý nghĩa |
| --- | --- |
| `--subreddit` | Bắt buộc; nhận `python` hoặc `r/python` |
| `--max-comments` | Bắt buộc; tối đa N comment hợp lệ, duy nhất trên **toàn bộ lần chạy** |
| `--max-posts` | Số bài mới tối đa cần duyệt, mặc định 100 |
| `--more-limit` | Số nhánh “load more” mở thêm mỗi bài, mặc định 8; đặt 0 để không mở thêm |
| `--db` | File SQLite, mặc định `data/reddit.sqlite3` |
| `--dry-run` | Vẫn đọc nguồn nhưng không tạo/thay đổi file database |
| `--retention-hours` | Thời gian giữ dữ liệu kể từ lần thu thập đầu, mặc định 48 giờ |

Comment `[deleted]`/`[removed]` và ID trùng trong lần chạy không tính vào N.
Comment đã có trong database và được cập nhật vẫn tính vào N; N không phải số
bản ghi mới cộng thêm hay giới hạn tổng kích thước database qua nhiều lần chạy.

Nếu nguồn không đủ dữ liệu, hoặc chạm `--max-posts`/giới hạn mở nhánh, có thể lấy
ít hơn N. Kết quả JSON trên stdout có `saved`, `created`, `updated`, `deleted`,
`duplicates`, `limit_reached`, `posts` và `unexpanded_branches`. `limit_reached`
chỉ cho biết đã đạt giới hạn N, không có nghĩa đã lấy hết comment. Trong dry-run,
`saved` là số dự kiến và kết quả có `would_save`/`would_delete`/`would_purge`.
Log tiến độ trên stderr có run ID; không ghi nội dung comment/credentials.
Kết nối có timeout connect/read 10/30 giây. Adapter thử lại HTTP 429/5xx tối đa
hai lần mỗi transport call và chờ theo `Retry-After` nếu có; PRAW/prawcore còn
xử lý giới hạn theo header và retry lỗi mạng có giới hạn. Sau khi hết retry,
lệnh thoát lỗi, giữ các bản ghi đã commit; chạy lại sẽ upsert theo ID.

API luôn đọc bài mới và comment mới trước; mẫu này **không ngẫu nhiên** và không
đại diện cho toàn subreddit. Reddit giới hạn listing; tăng N không đảm bảo lấy
đủ dữ liệu lịch sử. Giới hạn lưu N cũng không phải giới hạn chính xác số comment
API tải về: API tải theo batch, và mỗi lần mở nhánh có thể tải nhiều comment.

## Định dạng JSONL

Mỗi dòng là một JSON object. Đây là định dạng của tool, **không phải schema
export RFR được xác nhận**. Chuẩn hoá dữ liệu nguồn trước khi nhập:

```json
{"platform":"reddit","comment_id":"c1","content":"Nội dung giả lập","author_id":null,"author_name":null,"parent_id":"t3_p1","post_id":"t3_p1","comment_url":null,"created_at":1700000000,"like_count":3,"collected_at":null}
```

- Chỉ `comment_id` bắt buộc. `platform` có thể bỏ qua và mặc định là reddit.
  Các trường nội dung/tác giả/quan hệ/URL/thời gian tạo/điểm có thể bỏ qua hoặc null.
- `collected_at` trong file không được dùng để thay thời gian thu thập local:
  tool tự sinh lúc lưu lần đầu và giữ nguyên khi cập nhật để phục vụ retention.
- Có thể thêm `subreddit` trong file để lọc dữ liệu nhiều subreddit. Nếu không
  có trường này, dùng tên từ `--subreddit` làm ngữ cảnh của file.
- Vẫn nhận format cũ `id`, `body`, `score`, `created_utc`, `post_id` không có
  tiền tố. Format mới được ưu tiên; `post_id` được chuẩn hoá về `t3_...`.

Import chỉ lưu subreddit được chọn và dừng khi đạt N comment hợp lệ, duy nhất.
Một dòng lỗi làm dừng lệnh và báo số dòng; những dòng trước đã commit vẫn được
giữ. Chạy `--dry-run` trước nếu cần kiểm tra phần dữ liệu sẽ nhập.
Tool lưu tên/ID tác giả khi nguồn cung cấp, không lưu toàn bộ raw response.

## Cập nhật, xoá và thống kê

Với nguồn Data API được cấp quyền, làm mới comment đã lưu, xoá comment đã
deleted/removed hoặc không còn trả về trong response thành công:

```bash
python3 reddit_crawler.py sync --db data/reddit.sqlite3
python3 reddit_crawler.py purge --db data/reddit.sqlite3
python3 reddit_crawler.py stats --db data/reddit.sqlite3
```

`purge` không cần API. Các lệnh ghi dữ liệu đều purge dữ liệu quá hạn trước khi
thực hiện; `stats` chỉ đọc. Cập nhật không gia hạn `collected_at`.
Không có tiến trình nền: cần lập lịch chạy `purge`/`sync` khi lưu dữ liệu lâu dài.
Purge bật SQLite `secure_delete`; phải quản lý riêng bản sao lưu và file xuất.

Theo [Reddit Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki),
nội dung đã xoá phải được loại khỏi dữ liệu lưu. Với RFR, kiểm tra lại dữ liệu
theo bản export mới nhất và hướng dẫn của chương trình trước khi công bố kết
quả. Import không tự phát hiện ID vắng mặt trong export mới; muốn thay toàn bộ
snapshot, nhập export cập nhật vào file SQLite mới và xoá bản cũ theo yêu cầu.
Giá trị 48 giờ là mặc định của tool, không thay thế điều kiện lưu dữ liệu được
phê duyệt cho nghiên cứu.

Xem nội dung comment, mỗi comment một dòng, không cần lệnh `sqlite3` hay API:

```bash
python3 reddit_crawler.py show --db data/reddit.sqlite3 --limit 20
```

Đổi `20` thành số dòng muốn xem; bỏ `--limit` thì mặc định 10. Bỏ `--db` thì
dùng `data/reddit.sqlite3`. Comment thu thập gần nhất hiển thị trước:

```text
1. "I agree with this"
2. "Dòng đầu\nDòng sau"
3. None
```

Nội dung có xuống dòng được hiển thị bằng `\n` để mỗi comment nằm trên một dòng;
trường content thiếu hiển thị `None`. Database rỗng thì không in dòng comment
nào; database không tồn tại thì báo lỗi. Lệnh chỉ đọc, không purge, migrate hay
thay đổi dữ liệu, và hỗ trợ cả schema cũ.

Đọc thêm các trường bằng Python nếu máy chưa có lệnh `sqlite3`:

```bash
python3 - <<'PY'
import sqlite3
with sqlite3.connect('data/demo.sqlite3') as db:
    for row in db.execute('SELECT comment_id, parent_id, content FROM comments LIMIT 5'):
        print(row)
PY
```

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
```

Tests chạy offline, kiểm tra giới hạn trên nhiều bài, reply, tránh trùng,
parameterized SQL, sync theo batch, dữ liệu đã xoá, retention, import, dry-run,
đúng 11 cột, trường thiếu là NULL, ánh xạ tác giả/URL và chuyển đổi database cũ.
Tests public kiểm tra phân trang, reply, schema, không gửi credentials/cookie,
Retry-After, dừng 403 và báo lỗi JSON/mạng. Những tests này giả lập HTTP response.
Tests chẩn đoán phân biệt DNS Reddit/proxy/toàn hệ thống và xác nhận không in
credentials trong proxy URL.
Tests session kiểm tra cookie từ file local, phạm vi host/HTTPS, lỗi đầu vào,
thu thập vào SQLite và dừng 403 mà không ghi cookie vào log.
Tests tiến trình kiểm tra cập nhật trong lúc request đang chờ, đếm comment hợp
lệ, dry-run, tách JSON/log và dừng worker khi có lỗi hoặc Ctrl+C.
Không có kiểm thử mạng thật khi chưa có quyền/credentials.
