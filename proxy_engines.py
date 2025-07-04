
import os
import random
import requests

STATIC_PROXIES = [
    "http://51.81.245.3:17981",
    "http://128.199.202.122:8080",
    "http://198.23.143.74:80",
    "http://38.147.98.190:8080",
    "http://67.43.228.250:7015"
]

LIVE_STATIC_PROXIES = []

def is_proxy_working(proxy_url):
    try:
        r = requests.get("https://httpbin.org/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=5)
        return r.status_code == 200
    except:
        return False

def get_proxy_url(mode, url, scraperapi_key=None):
    mode = mode.lower()

    if mode == "scraperapi":
        # Use user-provided key if available, otherwise fall back to .env key
        key = scraperapi_key or os.getenv("SCRAPERAPI_KEY", "")
        if not key or key == "demo_key":
            print("[⚠️] ScraperAPI key is missing.")
            return url, None
        return f"http://api.scraperapi.com/?api_key={key}&url={url}", {}

    elif mode == "static":
        global LIVE_STATIC_PROXIES
        if not LIVE_STATIC_PROXIES:
            print("🔄 Checking static proxy health...")
            LIVE_STATIC_PROXIES = [p for p in STATIC_PROXIES if is_proxy_working(p)]

        if not LIVE_STATIC_PROXIES:
            print("[⚠️] No live static proxies available.")
            return url, None

        proxy = random.choice(LIVE_STATIC_PROXIES)
        print(f"🌐 Using static proxy: {proxy}")
        return url, {"http": proxy, "https": proxy}

    return url, None
