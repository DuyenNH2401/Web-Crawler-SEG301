import requests
from bs4 import BeautifulSoup as bs
from urllib.parse import urlsplit, urlunsplit
import re
from datetime import datetime
import hashlib
from db import init_db, save_comments

DB_PATH = "comments.db"
SEED_URL = "https://voz.vn/search/search?"
THREADS_KEYWORDS = ["Phân biệt vùng miền", "pbvm"]
THREADS_PER_SEARCH = 2
MAX_COMMENTS = 50
PAGE_PER_THREAD = 2
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_threads_url(seed_url, headers, threads_keywords, thread_per_search):
  urls = []
  for i in range(len(threads_keywords)):
    r = requests.get(seed_url, headers=headers, params={"keywords": threads_keywords}, timeout=15)
    soup = bs(r.text, "html.parser")
    a_tag = soup.select("h3.contentRow-title > a[href]", limit=thread_per_search)
    for a in a_tag:
      path = a.get("href")
      url = f"https://voz.vn{path}"
      urls.append(url)
  return urls

def thread_page(url, page):
    split = urlsplit(url)
    base = split.path.rsplit(sep="/", maxsplit=1)[0]
    split = split._replace(path=f"{base}/page-{1}")
    return urlunsplit(split)



def crawl_comments(urls, max_comments, headers, page_per_thread: int):
  comments = []
  count = 0
  for url in urls:
    for i in range(1, page_per_thread+1):
      page = thread_page(url, i)
      r = requests.get(page, headers=headers)
      soup = bs(r.text, "html.parser")
      div_tag = soup.select("div.bbWrapper")
      for div in div_tag:
        comment = div.get_text(separator=" ", strip=True)
        if count > max_comments:
          return comments
        else:
          count+=1
          comments.append(comment)
  return comments


def main():
  urls = get_threads_url(SEED_URL, HEADERS, THREADS_KEYWORDS, THREADS_PER_SEARCH)
  comments = crawl_comments(urls, MAX_COMMENTS, HEADERS, PAGE_PER_THREAD)
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  rows = []
  for c in comments:
    comment_id = hashlib.md5(c.encode()).hexdigest()
    rows.append(("voz", comment_id, c, "unknown", "unknown", "unknown", "unknown", now, 0))
 
  conn = init_db(DB_PATH)
  save_comments(conn, rows)
  conn.close()

if __name__ == "__main__":
  main()

