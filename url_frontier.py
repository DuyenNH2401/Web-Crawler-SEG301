"""
URL Frontier - quan ly hang doi URL cho crawler (Task 2, Task 6, Task 7)
Dung Breadth-First Search (BFS) bang collections.deque.
"""

from collections import deque


class URLFrontier:
    def __init__(self):
        self._queue = deque()
        self._queued_set = set()   # URL dang cho trong frontier (tranh add trung - Task 7)
        self.visited = set()       # URL da crawl roi (Task 7)

    def add(self, url, depth):
        """Them 1 URL vao frontier neu chua visited va chua nam san trong queue."""
        if url in self.visited or url in self._queued_set:
            return False
        self._queue.append((url, depth))
        self._queued_set.add(url)
        return True

    def add_seed(self, url):
        """Them seed URL o depth 0."""
        return self.add(url, depth=0)

    def next_url(self):
        """Lay URL tiep theo theo dung thu tu BFS (FIFO - popleft)."""
        if not self._queue:
            return None
        url, depth = self._queue.popleft()
        self._queued_set.discard(url)
        return url, depth

    def mark_visited(self, url):
        self.visited.add(url)

    def is_visited(self, url):
        return url in self.visited

    def is_empty(self):
        return len(self._queue) == 0

    def __len__(self):
        return len(self._queue)

    def print_frontier(self, limit=10):
        """In frontier hien tai (Task 2 - Output vi du)."""
        print("=" * 11 + " URL FRONTIER " + "=" * 11)
        for i, (url, depth) in enumerate(list(self._queue)[:limit], start=1):
            print(f"[{i}] {url} (depth={depth})")
        if len(self._queue) > limit:
            print(f"... va {len(self._queue) - limit} URL khac")
        print("=" * 36)
