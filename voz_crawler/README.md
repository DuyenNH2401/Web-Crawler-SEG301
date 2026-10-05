# Cào bình luận VOZ bằng Beautiful Soup

Crawler đọc các chủ đề công khai từ [box Chuyện trò linh tinh™](https://voz.vn/f/chuyen-tro-linh-tinhtm.17/), mở từng chủ đề và lấy bài trả lời. Bài đầu tiên của chủ đề là bài gốc nên không tính là bình luận. Chương trình không cần đăng nhập hoặc trình duyệt tự động.

## Chạy

Tại thư mục gốc dự án:

```powershell
python -m pip install -r requirements.txt
python main.py voz
```

Mặc định đọc 1 trang danh sách, tối đa 5 chủ đề, tối đa 2 trang của mỗi chủ đề. Có thể đổi giới hạn:

```powershell
python main.py voz --forum-pages 2 --max-threads 10 --thread-pages 3 --delay 2
```

Xem toàn bộ tùy chọn bằng `python main.py voz -h`. Bình luận được lưu vào `data/comments.db` cùng dữ liệu nền tảng khác và xuất ra `data/voz_comments.csv` (UTF-8, mở được trong Excel). Chạy lại không tạo bản ghi trùng trong database vì VOZ có ID riêng cho mỗi bài đăng. CSV chỉ chứa bình luận của lần chạy hiện tại và được ghi lại mỗi lần chạy.

Nếu muốn dùng đường dẫn khác:

```powershell
python main.py --db data/my_comments.db voz --output data/my_voz.csv
```

Đọc [GIAI_THICH_CODE.md](GIAI_THICH_CODE.md) để hiểu vai trò từng file và luồng dữ liệu. Crawler chỉ đọc HTML công khai; nếu VOZ đổi giao diện hoặc giới hạn truy cập, các bộ chọn trong `parser.py` có thể cần cập nhật.
