# TikTok crawler

Chạy từ thư mục gốc:

```powershell
python main.py tiktok "https://www.tiktok.com/@username/video/VIDEO_ID" --max 100 --replies --channel chrome
```

Crawler mở trình duyệt, cuộn khung bình luận và đọc các phản hồi TikTok gửi về. Kết quả được xuất ra `data/tiktok_comments.csv` và lưu vào `data/comments.db` chung. Hồ sơ trình duyệt mặc định ở `tiktok_profile/` và không được đưa vào Git.

Có thể chạy riêng bằng `python -m tiktok_crawler URL`. Dùng `python main.py tiktok -h` để xem các tùy chọn.
