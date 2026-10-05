# YouTube Comment Crawler - DPL Project

Cao comment (ca reply) tu video YouTube bang Python thuan (`requests`), luu vao
SQLite theo **dung schema chung cua nhom**, roi xuat CSV/JSONL de merge vao
database chinh.

Khong can trinh duyet, khong can dang nhap, khong can API key cua Google:
crawler goi dung API noi bo (InnerTube) ma trang web YouTube tu goi khi ban
cuon xuong phan binh luan. Comment YouTube la du lieu cong khai.

## 1. Cai dat

```bash
pip install -r requirements.txt
```

## 2. Chay

```bash
# 1 video
python main.py --url "https://www.youtube.com/watch?v=SGZkBoBsxsk"

# nhieu video: moi dong 1 link trong urls.txt
python main.py --input-file urls.txt

# cao xong xuat luon file de nop / merge
python main.py -i urls.txt --export data/exports/youtube.csv
```

| Tuy chon | Mac dinh | Y nghia |
| :--- | :--- | :--- |
| `--url / -u` | | Link video (dung nhieu lan duoc). Nhan `watch?v=`, `youtu.be/`, `/shorts/`, `/live/` |
| `--input-file / -i` | | File .txt, moi dong 1 link, dong `#` bi bo qua |
| `--max-comments / -n` | `0` (het) | So comment toi da moi video, tinh ca reply |
| `--sort` | `newest` | `newest` (Moi nhat, day du) hoac `top` (Hang dau) |
| `--no-replies` | | Chi lay comment goc |
| `--min-words` | `0` | Bo comment it hon N tu (vd `4` giong extension cu) |
| `--db` | `data/comments.db` | File SQLite |
| `--export / -o` | | Xuat toan bo DB ra `.csv` hoac `.jsonl` sau khi cao |

Xem / xuat du lieu da cao:

```bash
python view_db.py                              # tong quan + 10 comment moi nhat
python view_db.py --post SGZkBoBsxsk --limit 30
python view_db.py --search "bắc kỳ"
python view_db.py --export data/exports/SGZkBoBsxsk.csv --post SGZkBoBsxsk
```

Chay test (offline, khong can mang):

```bash
python -m unittest discover -s tests -v
```

## 3. Schema (thong nhat cua nhom)

| Cot | YouTube lay tu dau | Neu khong co |
| :--- | :--- | :--- |
| `platform` | hang so `youtube` | |
| `comment_id` | `commentId` (vd `Ugx...`; reply co dang `Ugx....xyz`) | comment bi bo |
| `content` | noi dung comment | comment rong bi bo |
| `author_id` | channel id `UC...` | `UNKNOWN` |
| `author_name` | ten hien thi / `@handle` | `UNKNOWN` |
| `parent_id` | `ROOT` cho comment goc, `comment_id` cua comment goc cho reply | |
| `post_id` | video id 11 ky tu | |
| `comment_url` | `https://www.youtube.com/watch?v=<video>&lc=<comment_id>` | |
| `created_at` | **gan dung**, xem muc 5 | = `collected_at` |
| `like_count` | so like (`1.2K` -> 1200) | `0` |
| `collected_at` | thoi diem bat dau cao video | |

- `UNIQUE(platform, comment_id)`: cao lai 1 video **khong tao dong trung**, chi cap
  nhat `content`, `author_name`, `like_count`, `collected_at`.
- File export **khong co cot `id`** vi database chinh tu sinh (`BIGSERIAL`).
- Thoi gian luu dang `YYYY-MM-DD HH:MM:SS`, mui gio **UTC+7** (doi trong
  `config.TIMEZONE` neu nhom chot mui gio khac).
- `schema_postgres.sql` co san cau lenh tao bang cho DB chinh va lenh import CSV
  (`ON CONFLICT DO NOTHING`).

## 4. Cach hoat dong

```
GET /watch?v=<id>&hl=en
   └─ HTML: ytInitialData (token comment dau tien) + INNERTUBE_API_KEY + clientVersion
POST /youtubei/v1/next {continuation: token}
   └─ trang 1: header 222 Comments + menu sap xep [Top, Newest]
POST /youtubei/v1/next {continuation: token Newest}
   └─ 20 comment goc + token trang sau
        └─ comment co reply -> POST /next {token reply} (lap qua moi trang "Show more replies")
   ... lap den khi het token hoac du --max-comments
```

- **2 dinh dang du lieu**: YouTube dang tra song song dinh dang cu
  (`commentRenderer`) va moi (`commentViewModel` - noi dung that nam rieng o
  `frameworkUpdates.entityBatchUpdate.mutations`, ghep lai bang `commentKey`).
  `youtube_parser.py` doc duoc ca hai.
- `hl=en` chi doi ngon ngu **giao dien** (chuoi thoi gian, so like) de parse on
  dinh; noi dung comment tieng Viet giu nguyen.
- Moi trang duoc ghi DB ngay -> Ctrl+C giua chung van giu phan da cao.
- Nghi `REQUEST_DELAY = 0.3s` giua cac request, tu thu lai 3 lan khi gap
  HTTP 429/5xx.

## 5. Han che can biet

- **`created_at` cua YouTube la gan dung.** YouTube chi tra chuoi tuong doi
  ("3 days ago"), crawler quy doi = `collected_at - 3 ngay`. Sai so tang theo
  don vi: "5 minutes ago" gan nhu chinh xac, "2 years ago" co the lech ca nam.
  Neu nhom can thoi gian chinh xac thi phai dung YouTube Data API v3 (can API
  key, gioi han quota).
- `like_count` cua comment nhieu like bi lam tron (YouTube hien `1.2K`).
- Comment bi YouTube an (spam / cho duyet) khong lay duoc.
- YouTube doi cau truc du lieu thi parser co the hong. Khi do chay
  `python -m unittest` van pass (vi dung du lieu gia lap) nhung cao that ra 0
  -> can cap nhat `youtube_parser.py`.

## 6. Cau truc thu muc

```
youtube-comment-crawler/
├── main.py              # CLI: doc link, cao, in thong ke, export
├── config.py            # moi tham so (delay, sort, mui gio, quy uoc UNKNOWN/ROOT...)
├── youtube_client.py    # goi mang: GET /watch, POST /youtubei/v1/next, retry
├── youtube_parser.py    # ham thuan: HTML/JSON -> comment tho (ca 2 dinh dang)
├── normalizer.py        # comment tho -> record dung schema (thoi gian, like, NOT NULL)
├── crawler.py           # vong lap trang / reply / gioi han, ghi DB tung trang
├── database.py          # SQLite theo schema + upsert + export CSV/JSONL
├── view_db.py           # xem / tim / export du lieu da cao
├── schema_postgres.sql  # schema DB chinh + lenh import CSV
├── urls.txt             # danh sach link mau
├── tests/               # unittest offline
└── data/                # comments.db, exports/
```
