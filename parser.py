"""
HTML parsing and link extraction/filtering module using BeautifulSoup.
Tasks 4 & 5: Extract Page Information and Filter Hyperlinks.
Specially optimized for News Article content extraction.
"""
import re
from datetime import datetime
from typing import Dict, List, Any, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

def is_domain_allowed(netloc: str, allowed_domains: List[str]) -> bool:
    """
    Check if the URL netloc belongs to or is a subdomain of the allowed domains list.
    Handles 'example.com', 'e.vnexpress.net'.
    """
    netloc = netloc.lower()
    for domain in allowed_domains:
        domain = domain.lower()
        if netloc == domain or netloc.endswith("." + domain):
            return True
    return False

def is_article_url(url: str) -> bool:
    """
    Kiểm tra xem một URL có phải là bài báo hợp lệ hay không:
    - Bắt buộc phải có đuôi .html
    - Không phải error.html hay các trang chuyên đề topic-
    - Có chứa mã số định danh bài viết VnExpress (ví dụ: -5122661.html)
    """
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    if not path.endswith(".html"):
        return False
        
    if "error.html" in path or "topic-" in path:
        return False
        
    return bool(re.search(r"-\d{5,}\.html$", path))

def parse_page_data(html_content: str, url: str, depth: int, status_code: int) -> Dict[str, Any]:
    """
    Extract structured information from HTML content (Task 4).
    Extracts: url, domain, title, clean article text content, depth, status code, timestamp.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Trích xuất Tiêu đề (Article Title)
    h1_tag = soup.find(["h1", "h2"], class_=re.compile(r"title_post|title-detail|title_news_detail")) or soup.find("h1")
    if h1_tag and h1_tag.get_text(strip=True):
        title = h1_tag.get_text(strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.get_text(strip=True)
    else:
        title = "Untitled Page"
        
    # Làm sạch hậu tố trang báo (ví dụ: ' - VnExpress International')
    title = re.sub(r"\s*-\s*VnExpress International.*$", "", title, flags=re.IGNORECASE).strip()
    
    # 2. Trích xuất Nội dung Bài báo (Article Content)
    lead_el = soup.find(class_=re.compile(r"lead_post_detail|description|lead_detail"))
    lead_text = lead_el.get_text(strip=True) if lead_el else ""
    
    body_container = soup.find(class_=re.compile(r"fck_detail|article-body|content_detail")) or soup.find("article")
    
    body_paragraphs: List[str] = []
    if body_container:
        for junk in body_container(["script", "style", "figure", "iframe", "noscript", "svg"]):
            junk.decompose()
            
        for p in body_container.find_all("p"):
            p_text = p.get_text(strip=True)
            if p_text and len(p_text) > 15:
                body_paragraphs.append(p_text)
                
    if body_paragraphs or lead_text:
        # Trang là bài báo hoàn chỉnh: ghép Lead + các đoạn văn bản chính
        parts = []
        if lead_text:
            parts.append(lead_text)
        parts.extend(body_paragraphs)
        content = "\n\n".join(parts)
    else:
        # Trang danh mục hoặc trang chủ (fallback): làm sạch và trích xuất text
        for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            element.decompose()
        content = soup.get_text(separator=" ", strip=True)
    
    # 3. Domain
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # 4. Crawled Timestamp
    crawled_at = datetime.now().isoformat()
    
    return {
        "url": url,
        "domain": domain,
        "title": title,
        "content": content,
        "depth": depth,
        "status_code": status_code,
        "crawled_at": crawled_at
    }

def extract_and_filter_links(
    html_content: str,
    current_url: str,
    allowed_domains: List[str],
    ignored_extensions: Set[str],
    ignored_schemes: Set[str],
    ignored_paths: Set[str] = None,
    articles_only: bool = True
) -> List[str]:
    """
    Extract hyperlinks from HTML and apply filtering rules (Task 5):
    1. Resolve relative URLs using urljoin.
    2. Ignore unsupported schemes (mailto:, javascript:, tel:, etc.).
    3. Ignore static assets (.jpg, .pdf, .css, .zip, etc.).
    4. Check domain whitelist against allowed_domains.
    5. Strip fragment anchors (#...).
    6. Filter out known error paths (e.g. /error.html).
    7. Filter by articles_only: BẮT BUỘC có đuôi .html và là bài báo thực sự!
    """
    if ignored_paths is None:
        ignored_paths = set()

    soup = BeautifulSoup(html_content, "html.parser")
    seen_in_page: Set[str] = set()
    valid_links: List[str] = []
    
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
            
        # Convert relative link to absolute URL
        absolute_url = urljoin(current_url, href)
        
        # Remove URL fragment / hash (#...)
        clean_url = absolute_url.split("#")[0].strip()
        if not clean_url or clean_url in seen_in_page:
            continue
        seen_in_page.add(clean_url)
        
        parsed = urlparse(clean_url)
        
        # Check scheme (only http and https allowed)
        if parsed.scheme.lower() not in ("http", "https"):
            continue
        if parsed.scheme.lower() in ignored_schemes:
            continue
            
        # Check domain constraint
        if not is_domain_allowed(parsed.netloc, allowed_domains):
            continue
            
        # Check file extension
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in ignored_extensions):
            continue
            
        # Check ignored path patterns
        if any(path_lower == ipath or path_lower.startswith(ipath) for ipath in ignored_paths):
            continue

        # NẾU BẬT CHẾ ĐỘ CHỈ CÀO BÀI BÁO: Kiểm tra bắt buộc đuôi .html và mã bài viết
        if articles_only:
            if not is_article_url(clean_url):
                # Bỏ qua các trang danh mục như /news/life/wellness, /news/news, etc.
                continue

        valid_links.append(clean_url)
            
    return valid_links
