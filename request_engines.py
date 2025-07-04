import requests
import httpx
from curl_cffi.requests import Session as CurlSession
from proxy_engines import get_proxy_url

def send_request(engine, method, url, headers=None, data=None, timeout=15, proxy_mode="none", scraperapi_key=None):
    url, proxies = get_proxy_url(proxy_mode, url, scraperapi_key)

    try:
        if engine == "requests":
            response = requests.request(method, url, headers=headers, data=data, timeout=timeout, proxies=proxies)
            return response

        elif engine == "httpx":
            with httpx.Client(proxies=proxies, timeout=timeout) as client:
                response = client.request(method, url, headers=headers, data=data)
                return response

        elif engine == "curl_cffi":
            with CurlSession(timeout=timeout, impersonate="chrome101") as session:
                response = session.request(method, url, headers=headers, data=data, proxies=proxies)
                return response

    except Exception as e:
        print(f"[❌ ERROR] Request failed using {engine} with proxy_mode={proxy_mode}: {e}")
        return None