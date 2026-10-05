# X crawler

Thư mục này chứa riêng mã cào bình luận X qua Chrome hoặc X API, cùng phần xuất CSV/JSONL. Chạy từ thư mục gốc dự án:

```powershell
python main.py x --post "https://x.com/username/status/1234567890123456789"
```

Cũng có thể chạy trực tiếp module X:

```powershell
python -m x_crawler --post "https://x.com/username/status/1234567890123456789"
```

Cả hai cách mặc định dùng `data/comments.db` và `data/x_browser_profile` ở thư mục gốc. Xem [README chung](../README.md) để biết cách đăng nhập và các tùy chọn.
