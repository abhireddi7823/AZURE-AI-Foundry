import os
import requests
from pathlib import Path

output = []

# ---------------- Azure Test ----------------

try:
    api_key = os.environ["AZURE_FOUNDRY_API_KEY"]
    endpoint = os.environ["AZURE_FOUNDRY_ENDPOINT"]
    deployment = os.environ["AZURE_FOUNDRY_DEPLOYMENT"]

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "model": deployment,
        "messages": [
            {
                "role": "user",
                "content": "Reply with Azure AI Foundry connection successful"
            }
        ],
        "temperature": 0
    }

    r = requests.post(
        f"{endpoint}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    output.append(f"Azure Status Code: {r.status_code}")

    if r.status_code == 200:
        answer = r.json()["choices"][0]["message"]["content"]
        output.append(f"Azure Result: {answer}")
    else:
        output.append(f"Azure Error: {r.text}")

except Exception as e:
    output.append(f"Azure Exception: {e}")

# ---------------- LRE Test ----------------

try:
    lre_host = os.environ["LRE_HOST"]
    lre_api_key = os.environ["LRE_API_KEY"]

    headers = {
        "Authorization": f"Basic {lre_api_key}"
    }

    r = requests.get(
        f"{lre_host}/loadtest/rest/domains",
        headers=headers,
        verify=False,
        timeout=60
    )

    output.append(f"LRE Status Code: {r.status_code}")
    output.append(f"LRE Response Length: {len(r.text)}")

except Exception as e:
    output.append(f"LRE Exception: {e}")

# ---------------- Summary ----------------

Path("analysis_output").mkdir(exist_ok=True)

with open("analysis_output/summary.md", "w") as f:
    f.write("# Connectivity Test\n\n")
    for line in output:
        f.write(f"- {line}\n")

print("\n".join(output))
