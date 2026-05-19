import base64
import zlib
import urllib.request

with open("architecture.mmd", "r") as f:
    mermaid_code = f.read()

compressed = zlib.compress(mermaid_code.encode('utf-8'), 9)
b64 = base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')
url = f"https://kroki.io/mermaid/png/{b64}"

req = urllib.request.Request(
    url, 
    data=None, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
)

with urllib.request.urlopen(req) as response, open("architecture.png", "wb") as out_file:
    out_file.write(response.read())

print("Saved architecture.png")
