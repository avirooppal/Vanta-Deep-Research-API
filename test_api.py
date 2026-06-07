import urllib.request
import json
import urllib.error

url = "http://localhost:8001/v1/research"
data = json.dumps({"query": "test"}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer drapi_live_foo", "Content-Type": "application/json"}, method="POST")

try:
    with urllib.request.urlopen(req) as f:
        print("Success:", f.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
