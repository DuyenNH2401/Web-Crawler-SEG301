import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from youtube_parser import extract_initial_data, extract_innertube_config

BASE_URL = "https://www.youtube.com"
FALLBACK_CLIENT_VERSION = "2.20260101.00.00"


class YouTubeError(Exception):
    """Lỗi."""


class YouTubeClient:
    def __init__(self, delay=None):
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": f"{config.LANGUAGE},vi;q=0.8",
        })
        self.session.cookies.set("SOCS", "CAI", domain=".youtube.com")
        retry = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=1.5,  # 0s, 1.5s, 3s... giua cac lan thu lai
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

        self.api_key = ""
        self.client_version = FALLBACK_CLIENT_VERSION
        self.request_count = 0

    # ---------- 1. Trang xem video ----------
    def fetch_watch_page(self, video_id):
        """Tra ve ytInitialData (dict). Dong thoi luu api_key / client_version."""
        try:
            response = self.session.get(
                f"{BASE_URL}/watch",
                params={"v": video_id, "hl": config.LANGUAGE, "gl": config.REGION},
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise YouTubeError(f"Khong ket noi duoc YouTube: {e}") from e
        self.request_count += 1
        if response.status_code != 200:
            raise YouTubeError(f"YouTube tra HTTP {response.status_code} cho video {video_id}.")

        html = response.text
        api_key, client_version = extract_innertube_config(html)
        self.api_key = api_key or self.api_key
        self.client_version = client_version or self.client_version

        initial_data = extract_initial_data(html)
        if initial_data is None:
            raise YouTubeError(
                "Khong doc duoc ytInitialData tu HTML (YouTube doi cau truc trang, "
                "hoac bi chuyen sang trang consent/captcha)."
            )
        return initial_data

    # ---------- 2. InnerTube /next ----------
    def next(self, continuation):
        if self.request_count and self.delay:
            time.sleep(self.delay)
        params = {"prettyPrint": "false"}
        if self.api_key:
            params["key"] = self.api_key
        body = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": self.client_version,
                    "hl": config.LANGUAGE,
                    "gl": config.REGION,
                }
            },
            "continuation": continuation,
        }
        try:
            response = self.session.post(
                f"{BASE_URL}/youtubei/v1/next",
                params=params,
                json=body,
                headers={
                    "X-Youtube-Client-Name": "1",
                    "X-Youtube-Client-Version": self.client_version,
                    "Origin": BASE_URL,
                },
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise YouTubeError(f"Loi mang khi goi YouTube API: {e}") from e
        self.request_count += 1
        if response.status_code != 200:
            raise YouTubeError(f"YouTube API tra HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as e:
            raise YouTubeError("YouTube API tra du lieu khong phai JSON.") from e
