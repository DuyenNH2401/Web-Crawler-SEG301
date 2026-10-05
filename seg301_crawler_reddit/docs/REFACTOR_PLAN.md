# Tách crawler thành các module

### Goal

Tách logic trong `reddit_crawler.py` vào package `reddit_app`, giữ nguyên các lệnh,
schema SQLite, hành vi thu thập, cookie, retry, tiến trình và dry-run.

### Assumptions

- Dùng Python 3.10+, không thêm dependency.
- `reddit_crawler.py` chỉ gọi `reddit_app.main.main()`.
- Test import trực tiếp từ module sở hữu chức năng; CLI hiện tại không đổi.
- Bộ 60 test hiện có đã pass trước khi refactor.

### Plan

1. Chụp phiên bản hiện tại và đầu ra trợ giúp CLI.
   - Files: bản sao trong `/tmp`, không đọc cookie hoặc database người dùng.
   - Change: lưu source, test và help để so sánh và rollback.
   - Verify: `python3 -W error::ResourceWarning -m unittest discover -s tests -q`.
2. Tách lớp dữ liệu và phần hạ tầng.
   - Files: `reddit_app/__init__.py`, `config.py`, `models.py`, `database.py`,
     `network.py`, `progress.py`.
   - Change: chuyển các hàm/class hiện tại; gom giá trị mặc định vào config;
     đưa truy vấn stats vào `database_stats()`.
   - Verify: import từng module; `python3 -m compileall -q reddit_app`.
3. Tách client, nghiệp vụ và CLI.
   - Files: `reddit_app/clients.py`, `crawler.py`, `parser.py`, `main.py`,
     `reddit_crawler.py`, `tests/test_*.py`.
   - Change: chuyển logic, nối import một chiều và cập nhật đường dẫn import test.
   - Verify: chạy đủ 60 test, so sánh help của tất cả subcommand trước/sau.
4. Cập nhật hướng dẫn và kiểm tra luồng chạy.
   - Files: `README.md`, `REFACTOR_PLAN.md`.
   - Change: ghi cấu trúc module và thứ tự đọc code cho người học.
   - Verify: import/stats/show/dry-run/purge qua subprocess với DB tạm;
     chạy lệnh CLI từ thư mục khác; kiểm tra cookie/PRAW vẫn chỉ đọc khi cần;
     chạy lại bộ test và compileall, rà soát import và thay đổi hành vi.

### Risks & mitigations

- Import vòng: models/config ở dưới; main chỉ điều phối, module khác không import main.
- Mất hành vi khi chuyển file: tái sử dụng thân hàm/class, test giữ nguyên assertions,
  so sánh help và chạy smoke check CLI trên dữ liệu giả lập.
- Cookie/DB thật: không đọc `.secrets` và không chạy lệnh ghi vào DB của người dùng.

### Rollback plan

Khôi phục source và test từ bản sao `/tmp`, xóa package vừa tạo và bỏ phần tài liệu
module mới. Không cần đổi schema hoặc khôi phục database.

### Verification results

- Bản sao trước refactor: `/tmp/reddit-refactor-l47w312d`.
- Cả 60 test pass trước và sau chuyển module; logic/assertion trong test không đổi,
  chỉ cập nhật đường dẫn import.
- Import độc lập cả 9 module thành công; không có import vòng hoặc import PRAW sớm.
- Đầu ra `--help` của CLI chính và 9 subcommand giống hệt trước refactor.
- So sánh AST của 22 hàm/class được chuyển, sau khi thay hằng cấu hình bằng giá trị:
  thân code giữ nguyên. `main()` dùng thêm `database_stats()` thay cho SQL nội tuyến.
- Smoke check subprocess của source cũ và mới cho cùng kết quả import, upsert,
  stats, show, dry-run, purge và schema SQLite; CLI chạy từ thư mục khác thành công.
- Đọc show/stats và dry-run giữ nguyên byte của DB; hiển thị multiline/None và
  lỗi limit/file thiếu vẫn đúng. Các kiểm tra chỉ dùng dữ liệu giả và DB tạm.
- `python3 -m compileall -q reddit_crawler.py reddit_app tests`: pass.
- Chưa chạy lại kết nối Reddit live; test HTTP sử dụng transport giả lập.

### Review

- Blockers: không phát hiện.
- Majors: không phát hiện.
- Minors: không phát hiện trong phạm vi refactor.
- Nits: không có yêu cầu chỉnh thêm.
- Overall summary + next actions: cấu trúc đã đúng thiết kế, README có bảng chức
  năng và thứ tự đọc; dùng các lệnh CLI hiện tại để chạy chương trình.
