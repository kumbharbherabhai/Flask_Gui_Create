import requests
url = 'https://exclusiveshop.com.pl/'
headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'accept-language': 'en-US,en;q=0.9', 'cache-control': 'max-age=0', 'priority': 'u=0, i', 'referer': 'https://www.google.com/', 'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate', 'sec-fetch-site': 'cross-site', 'sec-fetch-user': '?1', 'upgrade-insecure-requests': '1', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'}
data = '''{"name":"Bhavesh"}'''
response = requests.post(url, headers=headers, data=data)
print(response.status_code)
print(response.text)
print("[Request Sent]:", response.request.body)
print("[Response Status]:", response.status_code)

print("[Server Response]:")
try:
    print(response.json())  # will FAIL because Flipkart doesn't return JSON
except requests.exceptions.JSONDecodeError:
    print("❌ Server did not return JSON. Showing raw HTML instead...")
    print(response.text[:1000])  # show first 1000 characters of raw HTML
