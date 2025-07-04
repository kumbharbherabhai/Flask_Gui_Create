from flask import request, render_template, jsonify
from request_engines import send_request
import shlex
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import os

progress_data = {
    "running": False,
    "current": 0,
    "total": 0,
    "messages": [],
    "stop_flag": False,
    "method": None,
    "url": None,
    "headers": None,
    "data": None,
    "expected_text": None,
    "engine": "requests",
    "proxy_mode": "none",
    "concurrency": 1,
    "timeout": 15,
    "start_time": None,
    "end_time": None,
    "success_count": 0,
    "fail_count": 0,
    "error_count": 0,
    "scraperapi_key": None
}

class CurlConverter:
    def __init__(self, curl_command, post_data=None):
        self.curl_command = curl_command
        self.post_data = post_data

    def convert(self):
        parsed = shlex.split(self.curl_command) if self.curl_command else []
        method = "GET"
        url = ""
        headers = {}
        data = self.post_data  # Prioritize form POST data

        i = 0
        while i < len(parsed):
            part = parsed[i]
            if part.lower() == "curl":
                i += 1
                if i < len(parsed):
                    url = parsed[i].strip("'\"")
            elif part == "-X":
                i += 1
                if i < len(parsed):
                    method = parsed[i].upper()
            elif part == "-H":
                i += 1
                if i < len(parsed):
                    header_parts = parsed[i].split(":", 1)
                    if len(header_parts) == 2:
                        headers[header_parts[0].strip()] = header_parts[1].strip()
            elif part in ["-d", "--data", "--data-raw"] and not data:
                i += 1
                if i < len(parsed):
                    data = parsed[i]
                    method = "POST"  # default to POST if data exists and no form data
            elif part.startswith("http"):
                url = part.strip("'\"")
            i += 1

        if not url:
            raise ValueError("URL could not be extracted from the cURL command or provided.")
        return method, url, headers, data

def make_request(i):
    for attempt in range(2):  # Retry once
        try:
            if progress_data["stop_flag"]:
                return f"Iteration {i}: Stopped", None

            method = progress_data["method"]
            url = progress_data["url"]
            headers = progress_data["headers"]
            data = progress_data["data"]
            timeout = progress_data["timeout"]
            proxy_mode = progress_data.get("proxy_mode", "none")
            engine = progress_data["engine"]
            expected = progress_data["expected_text"]

            response = send_request(
                engine,
                method,
                url,
                headers=headers,
                data=data,
                timeout=timeout,
                proxy_mode=proxy_mode,
                scraperapi_key=progress_data["scraperapi_key"]
            )

            if not response and engine != "curl_cffi":
                print("⚠️ Retrying with curl_cffi fallback...")
                response = send_request(
                    "curl_cffi",
                    method,
                    url,
                    headers,
                    data,
                    timeout,
                    proxy_mode,
                    scraperapi_key=progress_data["scraperapi_key"]
                )

            if not response:
                raise Exception("Null response")

            content = response.text
            status_code = response.status_code
            found = expected in content if expected else True

            if found:
                progress_data["success_count"] += 1
                return f"Iteration {i}: OK (Status Code: {status_code})", None
            else:
                progress_data["fail_count"] += 1
                return f"Iteration {i}: FAIL (Status Code: {status_code})", None

        except Exception as e:
            if attempt == 1:
                progress_data["error_count"] += 1
                return f"Iteration {i}: ERROR - {str(e)}", e

        time.sleep(random.uniform(0.4, 0.8))

def worker():
    progress_data["running"] = True
    progress_data["stop_flag"] = False
    progress_data["start_time"] = datetime.datetime.now()
    results = []

    with ThreadPoolExecutor(max_workers=int(progress_data["concurrency"])) as executor:
        futures = {executor.submit(make_request, i): i for i in range(1, progress_data["total"] + 1)}
        for future in as_completed(futures):
            if progress_data["stop_flag"]:
                break
            result, _ = future.result()
            results.append(result)
            progress_data["current"] += 1

    def extract_iteration(msg):
        try:
            return int(msg.split()[1].strip(':'))
        except:
            return 0

    progress_data["messages"].extend(sorted(results, key=extract_iteration))
    progress_data["end_time"] = datetime.datetime.now()
    duration = (progress_data["end_time"] - progress_data["start_time"]).total_seconds()

    if not progress_data["stop_flag"]:
        progress_data["messages"].append("Execution completed.")
        progress_data["messages"].append(f"Total Time: {duration:.2f}s")
        progress_data["messages"].append(f"Success: {progress_data['success_count']}")
        progress_data["messages"].append(f"Fail: {progress_data['fail_count']}")
        progress_data["messages"].append(f"Error: {progress_data['error_count']}")

    progress_data["running"] = False

def register_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/start", methods=["POST"])
    def start():
        if progress_data["running"]:
            return jsonify({"error": "Execution already running."})

        curl_command = request.form.get("curl_command", "")
        post_data = request.form.get("post_data", "")
        expected_text = request.form.get("expected_text", "")
        iterations = request.form.get("iterations", "1")
        engine = request.form.get("engine", "requests")
        proxy_mode = request.form.get("proxy_mode", "none")
        http_method = request.form.get("http_method", "").upper()
        scraperapi_key = request.form.get("scraperapi_key", "")

        try:
            iterations = int(iterations)
            if iterations < 1:
                raise ValueError("Iterations must be 1 or more.")
        except:
            return jsonify({"error": "Invalid iteration number."})

        try:
            concurrency = int(request.form.get("concurrency", "1"))
            if concurrency < 1:
                raise ValueError("Concurrency must be 1 or more.")
            if concurrency > 100:
                concurrency = 100
        except:
            return jsonify({"error": "Invalid concurrency number."})

        try:
            method, url, headers, data = CurlConverter(curl_command, post_data).convert()
            if http_method:
                method = http_method
            elif post_data:
                method = "POST"  # Force POST if post_data is provided
        except Exception as e:
            return jsonify({"error": f"Error parsing cURL command: {e}"})

        progress_data.update({
            "current": 0,
            "total": iterations,
            "messages": ["Starting iterations..."],
            "stop_flag": False,
            "method": method,
            "url": url,
            "headers": headers,
            "data": data,
            "expected_text": expected_text,
            "running": True,
            "engine": engine,
            "proxy_mode": proxy_mode,
            "concurrency": concurrency,
            "timeout": 15,
            "start_time": None,
            "end_time": None,
            "success_count": 0,
            "fail_count": 0,
            "error_count": 0,
            "scraperapi_key": scraperapi_key
        })

        threading.Thread(target=worker).start()
        return jsonify({"status": "Execution started"})

    @app.route("/stop", methods=["POST"])
    def stop():
        progress_data["stop_flag"] = True
        progress_data["messages"].append("Execution stopped by user.")
        progress_data["messages"].append(f"Iterations stopped at: {progress_data['current']} of {progress_data['total']}")
        return jsonify({"status": "Stopping execution..."})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({
            "running": progress_data["running"],
            "current": progress_data["current"],
            "total": progress_data["total"],
            "messages": progress_data["messages"]
        })

    @app.route("/code", methods=["POST"])
    def code():
        curl_command = request.form.get("curl_command", "")
        post_data = request.form.get("post_data", "")
        engine = request.form.get("engine", "requests")
        proxy_mode = request.form.get("proxy_mode", "none")
        http_method = request.form.get("http_method", "").upper()
        scraperapi_key = request.form.get("scraperapi_key", "")

        try:
            method, url, headers, data = CurlConverter(curl_command, post_data).convert()
            if http_method:
                method = http_method
            elif post_data:
                method = "POST"
        except Exception as e:
            return jsonify({"code": f"Error: {e}"})

        code_str = ""
        if engine == "requests":
            code_str += "import requests\n"
            if proxy_mode == "scraperapi":
                code_str += f"scraperapi_key = '{scraperapi_key or os.getenv('SCRAPERAPI_KEY', 'YOUR_API_KEY')}' # Replace with your ScraperAPI key\n"
                code_str += f"url = 'http://api.scraperapi.com/?api_key={{scraperapi_key}}&url={url}'\n"
            else:
                code_str += f"url = '{url}'\n"
            if headers:
                code_str += f"headers = {headers}\n"
            if data:
                code_str += f"data = '''{data}'''\n"
            code_str += f"response = requests.{method.lower()}(url, headers=headers{', data=data' if data else ''})\n"
            if proxy_mode == "static":
                code_str += "# Note: For static proxies, add proxies={'http': 'proxy_url', 'https': 'proxy_url'} to the request\n"
            code_str += "print(response.status_code)\nprint(response.text)"

        elif engine == "httpx":
            code_str += "import httpx\n"
            if proxy_mode == "scraperapi":
                code_str += f"scraperapi_key = '{scraperapi_key or os.getenv('SCRAPERAPI_KEY', 'YOUR_API_KEY')}' # Replace with your ScraperAPI key\n"
                code_str += f"url = 'http://api.scraperapi.com/?api_key={{scraperapi_key}}&url={url}'\n"
            else:
                code_str += f"url = '{url}'\n"
            if headers:
                code_str += f"headers = {headers}\n"
            if data:
                code_str += f"data = '''{data}'''\n"
            code_str += f"with httpx.Client() as client:\n"
            code_str += f"    response = client.{method.lower()}(url, headers=headers{', data=data' if data else ''})\n"
            if proxy_mode == "static":
                code_str += "# Note: For static proxies, add proxies={'http': 'proxy_url', 'https': 'proxy_url'} to the client\n"
            code_str += "    print(response.status_code)\n    print(response.text)"

        elif engine == "curl_cffi":
            code_str += "from curl_cffi import requests as curl_requests\n"
            if proxy_mode == "scraperapi":
                code_str += f"scraperapi_key = '{scraperapi_key or os.getenv('SCRAPERAPI_KEY', 'YOUR_API_KEY')}' # Replace with your ScraperAPI key\n"
                code_str += f"url = 'http://api.scraperapi.com/?api_key={{scraperapi_key}}&url={url}'\n"
            else:
                code_str += f"url = '{url}'\n"
            if headers:
                code_str += f"headers = {headers}\n"
            if data:
                code_str += f"data = '''{data}'''\n"
            code_str += f"with curl_requests.Session() as session:\n"
            code_str += f"    response = session.{method.lower()}(url, headers=headers{', data=data' if data else ''})\n"
            if proxy_mode == "static":
                code_str += "# Note: For static proxies, add proxies={'http': 'proxy_url', 'https': 'proxy_url'} to the session\n"
            code_str += "    print(response.status_code)\n    print(response.text)"

        return jsonify({"code": code_str})