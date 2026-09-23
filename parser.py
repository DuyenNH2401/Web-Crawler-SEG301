"""
Parser - trich xuat thong tin trang (Task 4, mo rong loc noi dung ben
trong) va trich xuat/loc hyperlink (Task 5, loc o ngoai).
"""

import copy
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config


def normalize_domain(netloc):
    """Bo tien to 'www.' de coi www.globaltimes.cn va globaltimes.cn la cung 1 domain."""
    netloc = netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def normalize_url(url):
    """Chuan hoa URL: bo fragment (#...), bo dau '/' thua o cuoi path (Task 7)."""
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        "",  # bo fragment
    ))
    return normalized


def extract_page_info(url, html, depth, status_code):
    """
    Task 4: trich xuat URL, domain, title, noi dung text, depth,
    status_code, timestamp - CHI lay phan noi dung bai viet that su
    (loc theo config.ARTICLE_CONTENT_SELECTORS / EXCLUDE_SELECTORS).

    Tra ve (page_info_dict_hoac_None, soup_GOC):
    - soup_GOC khong bi thay doi gi ca, de crawler.py van trich link
      day du (Task 5) du trang nay co duoc luu vao database hay khong.
    - page_info se la None neu REQUIRE_ARTICLE_MATCH=True ma khong tim
      thay khoi bai viet nao khop ARTICLE_CONTENT_SELECTORS (vd day la
      trang danh muc/trang chu, khong phai bai viet that).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Lam 1 BAN SAO rieng de loc/trich content. KHONG .decompose() truc
    # tiep tren soup goc, vi lam vay se xoa luon cac the <a> nam trong
    # nav/footer, khien extract_links() (goi ben crawler.py) mat bot
    # link va Frontier can kiet nhanh hon binh thuong.
    content_soup = copy.deepcopy(soup)
    for selector in config.EXCLUDE_SELECTORS:
        for tag in content_soup.select(selector):
            tag.decompose()

    title_tag = soup.title
    title = title_tag.get_text(strip=True) if title_tag else ""

    article_node = None
    for selector in config.ARTICLE_CONTENT_SELECTORS:
        found = content_soup.select_one(selector)
        if found is not None:
            article_node = found
            break

    if article_node is not None:
        text_content = article_node.get_text(separator=" ", strip=True)
    elif config.REQUIRE_ARTICLE_MATCH:
        # Khong khop selector nao va bat buoc phai khop -> khong phai
        # bai viet that (vd trang danh muc) -> bao crawler.py bo qua.
        return None, soup
    else:
        text_content = content_soup.get_text(separator=" ", strip=True)

    domain = normalize_domain(urlparse(url).netloc)

    page_info = {
        "url": url,
        "domain": domain,
        "title": title,
        "content": text_content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    return page_info, soup


def is_valid_url(url):
    """Task 5: loai bo scheme khong phai http/https va file khong phai HTML."""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    path_lower = parsed.path.lower()
    for ext in config.IGNORED_EXTENSIONS:
        if path_lower.endswith(ext):
            return False

    return True


def is_allowed_domain(url):
    """Task 5: chi giu URL thuoc ALLOWED_DOMAINS."""
    domain = normalize_domain(urlparse(url).netloc)
    allowed = {normalize_domain(d) for d in config.ALLOWED_DOMAINS}
    return domain in allowed


def extract_links(soup, current_url):
    """
    Task 5: lay tat ca the <a href>, bo scheme dac biet (mailto/javascript/tel),
    chuyen thanh absolute URL bang urljoin, chuan hoa, roi loc theo domain/extension.

    Luu y: nhan "soup GOC" (chua bi decompose gi) tu extract_page_info(),
    nen luon lay du link ke ca khi trang do khong duoc luu vao pages.
    """
    candidates = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue

        scheme_part = href.split(":", 1)[0].lower()
        if scheme_part in config.IGNORED_SCHEMES:
            continue

        absolute_url = urljoin(current_url, href)
        absolute_url = normalize_url(absolute_url)
        candidates.append(absolute_url)

    valid_links = []
    for link in candidates:
        if is_valid_url(link) and is_allowed_domain(link):
            valid_links.append(link)

    return valid_links
