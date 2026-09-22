"""
url_frontier.py - Tasks 2, 6 and 7: the BFS queue of URLs waiting to be
crawled, plus duplicate detection.
"""

from collections import deque

from parser import normalize_url


class URLFrontier:
    """
    A breadth-first URL frontier.

    Each entry is a (url, depth) pair. Because a deque is appended on the right
    and popped on the left, every URL at depth N is handed out before any URL
    at depth N+1 - that is what makes the traversal BFS rather than DFS.

    Three collections are kept:
      queued  - URLs currently waiting in the queue
      visited - URLs already fetched
      seen    - queued + visited; the duplicate test (Task 7)
    """

    def __init__(self):
        self._queue = deque()
        self.visited = set()
        self.seen = set()

    # ------------------------------------------------------------ adding --
    def add(self, url, depth):
        """
        Add a URL at the given depth.

        Returns True if it was accepted, False if it is a duplicate. Depth is
        enforced by the caller (Task 6) so that the rejection can be counted.
        """
        url = normalize_url(url)
        if url in self.seen:
            return False
        self.seen.add(url)
        self._queue.append((url, depth))
        return True

    def add_seeds(self, seed_urls):
        for url in seed_urls:
            self.add(url, 0)

    # ----------------------------------------------------------- reading --
    def next(self):
        """Pop the next (url, depth) pair, or None when the frontier is empty."""
        if not self._queue:
            return None
        return self._queue.popleft()

    def mark_visited(self, url):
        self.visited.add(normalize_url(url))

    def has_visited(self, url):
        return normalize_url(url) in self.visited

    # ------------------------------------------------------------ status --
    def __len__(self):
        return len(self._queue)

    def is_empty(self):
        return not self._queue

    def show(self, limit=10):
        """Print the head of the frontier, in the format Task 2 asks for."""
        print("========== URL FRONTIER ==========")
        if not self._queue:
            print("(empty)")
            return
        for i, (url, depth) in enumerate(list(self._queue)[:limit], start=1):
            print(f"[{i}] (depth {depth}) {url}")
        remaining = len(self._queue) - limit
        if remaining > 0:
            print(f"... and {remaining} more")
