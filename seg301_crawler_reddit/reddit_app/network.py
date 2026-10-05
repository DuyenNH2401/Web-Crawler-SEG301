"""Retry HTTP, phân loại lỗi kết nối và kiểm tra DNS/proxy."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
import errno
import math
import socket
import ssl
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from .config import LOG, MAX_HTTP_ATTEMPTS


def request_with_backoff(send: Callable[[], Any], *, sleep: Callable[[float], None] = time.sleep) -> Any:
    """Retry read requests/ OAuth token requests, at most twice per transport call."""
    for attempt in range(MAX_HTTP_ATTEMPTS):
        started = time.monotonic()
        response = send()
        LOG.info("request attempt=%d status=%d elapsed_ms=%d", attempt + 1, response.status_code,
                 (time.monotonic() - started) * 1000)
        retryable = response.status_code == 429 or 500 <= response.status_code < 600
        if not retryable or attempt == MAX_HTTP_ATTEMPTS - 1:
            return response
        delay = float(2 ** attempt)
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                parsed = float(retry_after)
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(retry_after).timestamp() - time.time()
                except (TypeError, ValueError, OverflowError):
                    parsed = delay
            if math.isfinite(parsed):
                delay = max(delay, parsed)
        response.close()
        LOG.warning("retry status=%d delay_seconds=%.1f", response.status_code, delay)
        sleep(delay)
    raise AssertionError("unreachable")


def network_error_message(error: BaseException) -> str:
    """Expose the error category/code, never arbitrary proxy URLs or secret text."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    kind = type(reason).__name__ if isinstance(reason, BaseException) else type(error).__name__
    code = getattr(reason, "errno", None)
    detail = kind + (f", errno={code}" if isinstance(code, int) else "")
    if isinstance(reason, socket.gaierror):
        message = "DNS không phân giải được hostname; kiểm tra DNS/mạng của môi trường đang chạy"
    elif isinstance(reason, ssl.SSLCertVerificationError):
        message = "lỗi chứng chỉ TLS; kiểm tra kho CA của Python và chứng chỉ proxy nếu có"
    elif isinstance(reason, ssl.SSLError):
        message = "lỗi TLS khi kết nối HTTPS; kiểm tra cấu hình TLS/proxy"
    elif isinstance(reason, TimeoutError) or code == errno.ETIMEDOUT:
        message = "timeout khi kết nối/đọc Reddit; kiểm tra mạng/proxy và giá trị --timeout"
    elif isinstance(reason, ConnectionRefusedError) or code == errno.ECONNREFUSED:
        message = "kết nối TCP bị từ chối; kiểm tra địa chỉ/cổng proxy và kết nối mạng"
    elif code in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
        message = "không có đường mạng tới đích; kiểm tra kết nối và cấu hình mạng"
    else:
        message = "lỗi kết nối mạng; kiểm tra mạng/proxy của môi trường đang chạy"
    return f"không kết nối được Reddit: {message} ({detail})"


def diagnose_network() -> dict[str, Any]:
    """Read-only DNS/proxy inspection using the crawler's Python environment."""
    target = "www.reddit.com"
    proxy_url = urllib.request.getproxies().get("https")
    proxy = dict(configured=bool(proxy_url), active_for_reddit=False, hostname=None)
    invalid_proxy = False
    if proxy_url:
        proxy["active_for_reddit"] = not urllib.request.proxy_bypass(target)
        try:
            parsed = urllib.parse.urlsplit(proxy_url if "://" in proxy_url else "http://" + proxy_url)
            proxy["hostname"] = parsed.hostname
            invalid_proxy = not bool(parsed.hostname)
            parsed.port  # Validate without printing the URL or credentials.
        except ValueError:
            invalid_proxy = True
    hosts = [target, "pypi.org"]
    if proxy["active_for_reddit"] and proxy["hostname"] and not invalid_proxy:
        hosts.append(proxy["hostname"])
    checks = []
    for host in dict.fromkeys(hosts):
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            checks.append(dict(hostname=host, status="ok"))
        except OSError as error:
            checks.append(dict(hostname=host, status="error", error_type=type(error).__name__,
                               errno=error.errno if isinstance(error.errno, int) else None))
    status = {check["hostname"]: check["status"] for check in checks}
    if proxy["active_for_reddit"] and invalid_proxy:
        assessment = "invalid_proxy_configuration"
    elif proxy["active_for_reddit"]:
        assessment = "proxy_dns_failure" if status.get(proxy["hostname"]) == "error" else "proxy_dns_ok"
    elif status[target] == "error" and status["pypi.org"] == "error":
        assessment = "general_dns_failure"
    elif status[target] == "error":
        assessment = "reddit_dns_failure"
    else:
        assessment = "dns_ok"
    return dict(proxy=proxy, dns_checks=checks, assessment=assessment,
                note="DNS thành công chưa xác nhận được kết nối HTTPS hoặc quyền truy cập Reddit")
