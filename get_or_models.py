import urllib.request
import json
with urllib.request.urlopen("https://openrouter.ai/api/v1/models") as response:
    data = json.loads(response.read().decode())
    for model in data.get("data", []):
        if "free" in model["id"].lower():
            print(model["id"])
