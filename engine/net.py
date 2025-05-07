import requests
import random
import time

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
]

def get(url: str, retries: int = 2, timeout: int = 10, headers: dict = None) -> requests.Response:
    last_error = None
    for attempt in range(retries):
        try:
            all_headers = headers or {}
            all_headers["User-Agent"] = random.choice(USER_AGENTS)
            response = requests.get(url, headers=all_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error = e
            time.sleep(1 + attempt)
    raise last_error
