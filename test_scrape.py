import requests
import re

url = 'https://www.instagram.com/ai.with.arthisha/'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get(url, headers=headers)
print("Status code:", r.status_code)

# Try meta tag
m1 = re.search(r'content="([\d\.,MKmk]+)\s+Followers,', r.text)
if m1:
    print("Found via meta tag:", m1.group(1))
else:
    print("Not found in meta")
