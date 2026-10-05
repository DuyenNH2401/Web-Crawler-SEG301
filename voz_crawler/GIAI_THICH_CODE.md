# Giải thích code crawler VOZ

## Các file

- `crawler.py`: toàn bộ phần lấy trang, đọc HTML, lưu bình luận và nhận tham số.
- `__main__.py`: cho phép chạy riêng bằng `python -m voz_crawler`.
- `../main.py`: thêm lệnh `voz` vào menu chung của dự án.

## Luồng chạy

1. `main()` đọc giới hạn số trang, số chủ đề và đường dẫn lưu dữ liệu. Các giới hạn giúp lần chạy đầu tiên không tải quá nhiều trang.
2. `crawl()` tạo một `requests.Session`, tải trang box F17 bằng `get_page()`, rồi dùng `threads_on_page()` tìm liên kết các chủ đề. `next_page()` tìm nút **Sau** nếu cần đọc tiếp danh sách.
3. Với mỗi chủ đề, `crawl()` tải tối đa `--thread-pages` trang. `comments_on_page()` tìm các thẻ `article.message--post` chứa bài đăng. Ở trang đầu, bài đăng đầu tiên là bài gốc nên được bỏ qua; các bài còn lại là bình luận.
4. Mỗi bình luận lấy ID bài đăng, tên/ID tác giả, nội dung và thời gian. Thời gian được đổi sang UTC. Phần trích dẫn trong bình luận được bỏ để tránh lặp lại lời của người khác.
5. `upsert_comments()` lưu vào bảng `comments` chung với `platform='voz'`. Khóa `(platform, comment_id)` giúp chạy lại mà không tạo bản sao. Cuối cùng chương trình ghi CSV để xem nhanh.

## Các bộ chọn HTML chính

| Bộ chọn | Ý nghĩa |
| --- | --- |
| `.structItem--thread` | Một chủ đề ở trang danh sách |
| `.structItem-title a[data-tp-primary]` | Tên và URL chủ đề |
| `article.message--post[data-content]` | Một bài đăng trong chủ đề |
| `.message-body .bbWrapper` | Nội dung bài đăng |
| `.message-name a` | Tác giả |
| `.message-attribution-main time[datetime]` | Thời gian đăng |
| `a.pageNav-jump--next` | Liên kết sang trang kế tiếp |

Ví dụ, `data-content="post-123"` cho biết ID bình luận là `123`. `post_id` trong database là ID chủ đề, không phải ID bình luận. VOZ hiển thị thảo luận dạng phẳng nên `parent_id` được ghi `UNKNOWN`; `like_count` đặt `0` vì crawler cơ bản này không bóc tách lượt thích. Bình luận chỉ có ảnh mà không có chữ sẽ bị bỏ qua.

Nếu trang trả lỗi HTTP, `get_page()` dừng và báo lỗi. `--delay` thêm khoảng nghỉ giữa các lần tải. Crawler chỉ duyệt trang chủ đề công khai, không mở các đường dẫn tài khoản hay đường dẫn bài đăng riêng.
