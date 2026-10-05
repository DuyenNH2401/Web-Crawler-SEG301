import httpx
import pytest

from crawler.threads.collector import CollectionError, Collector


def collector_with(handler, monkeypatch):
    monkeypatch.setattr("crawler.threads.collector.time.sleep", lambda _: None)
    collector = Collector()
    collector.client.close()
    collector.client = httpx.Client(transport=httpx.MockTransport(handler))
    return collector


def test_robots_metadata_is_read_with_users_denial_check_disabled(monkeypatch):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    with collector_with(handler, monkeypatch) as collector:
        collector._allowed("https://www.threads.com/@a/post/abc")
    assert requested == ["https://www.threads.com/robots.txt"]


def test_http_retries_are_bounded(monkeypatch):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(429)

    with (
        collector_with(handler, monkeypatch) as collector,
        pytest.raises(CollectionError, match="RATE_LIMITED"),
    ):
        collector._request("https://www.threads.com/robots.txt")
    assert len(requests) == 3


def test_http_snapshot_and_declared_crawl_delay(monkeypatch):
    def handler(request):
        text = (
            "User-agent: *\nAllow: /\nCrawl-delay: 5"
            if request.url.path == "/robots.txt"
            else "page"
        )
        return httpx.Response(200, text=text)

    with collector_with(handler, monkeypatch) as collector:
        assert list(collector.pages("https://www.threads.com/@a/post/abc")) == ["page"]
        assert collector.delay == 5


def test_cleanup_closes_all_resources_even_when_one_is_interrupted():
    import signal

    closed = []

    class Resource:
        def __init__(self, name, interrupt=False):
            self.name, self.interrupt = name, interrupt

        def close(self):
            closed.append(self.name)
            if self.interrupt:
                raise KeyboardInterrupt

        def stop(self):
            self.close()

    collector = Collector()
    collector.client.close()
    collector.context = Resource("context", True)
    collector.browser = Resource("browser")
    collector.playwright = Resource("driver")
    collector.client = Resource("http")
    handler = signal.getsignal(signal.SIGINT)
    with pytest.raises(KeyboardInterrupt):
        collector.__exit__(None, None, None)
    assert closed == ["context", "browser", "driver", "http"]
    assert signal.getsignal(signal.SIGINT) == handler


def test_content_wait_uses_ready_markers_instead_of_request_delay():
    calls = []

    class Page:
        def wait_for_function(self, expression, **kwargs):
            calls.append((expression, kwargs))

    Collector._wait_ready(Page(), "threads_search_results")
    expression, kwargs = calls[0]
    assert "No results" in expression
    assert "data-pressable-container" in expression
    assert kwargs == {"arg": "threads_search_results", "timeout": 30000}


def test_login_saves_only_an_authenticated_session(monkeypatch, tmp_path):
    class Page:
        def goto(self, *args, **kwargs):
            pass

        def close(self):
            pass

    class Context:
        def new_page(self):
            return Page()

        def cookies(self, *args):
            return [{"name": "sessionid", "value": "test-session"}]

        def storage_state(self, path):
            from pathlib import Path

            Path(path).write_text('{"cookies": [], "origins": []}', encoding="utf-8")

        def close(self):
            pass

    with Collector() as collector:
        collector.context = Context()
        monkeypatch.setattr(collector, "_start_browser", lambda: None)
        monkeypatch.setattr("builtins.input", lambda _: "")
        output = tmp_path / "browser_storage_state.json"
        collector.login(output)
        assert output.exists()


def test_ctrl_c_finishes_browser_call_before_interrupting():
    import signal

    from crawler.common.interrupts import finish_browser_call

    handler = signal.getsignal(signal.SIGINT)
    finished = []
    with pytest.raises(KeyboardInterrupt), finish_browser_call():
        # Exercise the actual installed handler without terminating the test process.
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        finished.append("browser call settled")
    assert finished == ["browser call settled"]
    assert signal.getsignal(signal.SIGINT) == handler
