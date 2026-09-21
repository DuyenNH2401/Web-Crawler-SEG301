"""
URL Frontier module implementing FIFO queue (Breadth-First Search - BFS).
Tasks 2, 6, 7: URL Frontier, Depth Control, Duplicate Avoidance.
"""
from collections import deque
from typing import Tuple, Optional, Set, List
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """
    Normalize a URL to ensure reliable deduplication:
    1. Strip whitespace
    2. Lowercase scheme and netloc (domain)
    3. Remove fragment identifiers (#anchor)
    4. Remove trailing slash for path consistency (except root '/')
    """
    url = url.strip()
    parsed = urlparse(url)
    
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Strip default ports if present
    if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]
        
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if not path:
        path = "/"
        
    # Reassemble without query fragment
    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
    return normalized

class URLFrontier:
    """
    Breadth-First Search (BFS) URL Frontier.
    Maintains:
    - deque of (url, depth) tuples
    - visited set for URLs already fetched
    - seen/enqueued set to avoid enqueuing duplicates
    """
    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.queue: deque[Tuple[str, int]] = deque()
        self.visited: Set[str] = set()
        self.seen: Set[str] = set()
        
        # Statistics
        self.total_discovered: int = 0
        self.total_skipped: int = 0

    def add_url(self, url: str, depth: int) -> bool:
        """
        Attempt to add a URL with its crawl depth to the frontier.
        Enforces depth constraints and deduplication.
        Returns True if accepted and enqueued, False if skipped.
        """
        self.total_discovered += 1
        clean_url = normalize_url(url)
        
        # Check depth constraint (Task 6)
        if depth > self.max_depth:
            self.total_skipped += 1
            return False

        # Check duplicate avoidance (Task 7)
        if clean_url in self.seen or clean_url in self.visited:
            self.total_skipped += 1
            return False

        # Accept and add to queue
        self.seen.add(clean_url)
        self.queue.append((clean_url, depth))
        return True

    def add_seeds(self, seed_urls: List[str]) -> int:
        """Add initial seed URLs at depth 0."""
        added = 0
        for seed in seed_urls:
            if self.add_url(seed, depth=0):
                added += 1
        return added

    def get_next(self) -> Optional[Tuple[str, int]]:
        """
        Retrieve and remove the next (url, depth) from the queue (FIFO).
        Marks the URL as visited.
        """
        if self.is_empty():
            return None
        url, depth = self.queue.popleft()
        self.visited.add(url)
        return url, depth

    def is_empty(self) -> bool:
        """Check if the frontier has no remaining URLs."""
        return len(self.queue) == 0

    def __len__(self) -> int:
        """Return the number of URLs currently queued."""
        return len(self.queue)
