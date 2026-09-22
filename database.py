"""
Database management module for storing crawled web pages and links using SQLite.
Task 8: Store Crawled Data in SQLite
"""
import os
import sqlite3
from typing import Dict, List, Any, Optional

from models import Digest

def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a connection to the SQLite database and ensure directory exists."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str) -> None:
    """Initialize SQLite database tables."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Table 1: pages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                domain TEXT,
                title TEXT,
                content TEXT,
                depth INTEGER,
                status_code INTEGER,
                crawled_at TEXT
            );
        """)
        
        # Table 2: links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                target_url TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                content TEXT,
                article_count INTEGER,
                created_at TEXT
            );
        """)
        conn.commit()

def insert_page(db_path: str, page_data: Dict[str, Any]) -> bool:
    """
    Insert a crawled page into the pages table.
    Returns True if inserted successfully, False if duplicate or failed.
    """
    sql = """
        INSERT OR IGNORE INTO pages (url, domain, title, content, depth, status_code, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                page_data.get("url"),
                page_data.get("domain"),
                page_data.get("title"),
                page_data.get("content"),
                page_data.get("depth"),
                page_data.get("status_code"),
                page_data.get("crawled_at")
            ))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[DB Error] Failed to insert page {page_data.get('url')}: {e}")
        return False

def insert_links(db_path: str, source_url: str, target_urls: List[str]) -> int:
    """
    Insert extracted hyperlinks into the links table.
    Returns the number of links inserted.
    """
    if not target_urls:
        return 0
    
    sql = "INSERT INTO links (source_url, target_url) VALUES (?, ?)"
    records = [(source_url, target) for target in target_urls]
    
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, records)
            conn.commit()
            return len(records)
    except sqlite3.Error as e:
        print(f"[DB Error] Failed to insert links for {source_url}: {e}")
        return 0

def insert_digest(db_path: str, digest: Digest) -> bool:
    """Store one combined digest from a crawl run."""
    sql = """
        INSERT INTO digests (topic, content, article_count, created_at)
        VALUES (?, ?, ?, ?)
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                digest.topic,
                digest.content,
                len(digest.articles),
                digest.created_at,
            ))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[DB Error] Failed to insert digest: {e}")
        return False

def get_summary_stats(db_path: str) -> Dict[str, Any]:
    """Retrieve statistical aggregations from the database for the summary report."""
    stats: Dict[str, Any] = {
        "pages_crawled": 0,
        "unique_links_stored": 0,
        "depth_counts": {},
        "status_code_counts": {}
    }
    
    if not os.path.exists(db_path):
        return stats
        
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            
            # Total crawled pages
            cursor.execute("SELECT COUNT(*) FROM pages")
            stats["pages_crawled"] = cursor.fetchone()[0]
            
            # Unique target URLs in links table
            cursor.execute("SELECT COUNT(DISTINCT target_url) FROM links")
            stats["unique_links_stored"] = cursor.fetchone()[0]
            
            # Breakdown by depth
            cursor.execute("SELECT depth, COUNT(*) FROM pages GROUP BY depth ORDER BY depth ASC")
            for row in cursor.fetchall():
                stats["depth_counts"][row[0]] = row[1]
                
            # Breakdown by status code
            cursor.execute("SELECT status_code, COUNT(*) FROM pages GROUP BY status_code ORDER BY status_code ASC")
            for row in cursor.fetchall():
                stats["status_code_counts"][row[0]] = row[1]
                
    except sqlite3.Error as e:
        print(f"[DB Error] Failed to compute stats: {e}")
        
    return stats
