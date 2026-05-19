import base64
import json
import urllib.request
import ssl

with open("architecture.mmd", "r") as f:
    mermaid_code = f.read()

payload = json.dumps({"code": mermaid_code, "mermaid": {"theme": "default"}})
b64 = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8').rstrip('=')
url = f"https://mermaid.ink/img/{b64}"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    url, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
)

print(f"Downloading from mermaid.ink...")
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as response, open("architecture.png", "wb") as out_file:
        out_file.write(response.read())
    print("Saved architecture.png")
except Exception as e:
    print(f"Failed: {e}")
