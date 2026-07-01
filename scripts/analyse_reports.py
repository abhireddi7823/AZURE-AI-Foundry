import os
import requests
from pathlib import Path

results = []

# -------------------------
# Azure AI Foundry Test
# -------------------------

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

    response = requests.post(
        f"{endpoint}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    results.append(f"Azure Status Code: {response.status_code}")

    if response.status_code == 200:
        answer = response.json()["choices"][0]["message"]["content"]
        results.append(f"Azure Response: {answer}")
    else:
        results.append(f"Azure Error: {response.text}")

except Exception as e:
    results.append(f"Azure Exception: {str(e)}")

# -------------------------
# LRE Connectivity Test
# -------------------------

try:
    lre_host = os.environ["LRE_HOST"]
    lre_api_key = os.environ["LRE_API_KEY"]

    headers = {
        "Authorization": f"Basic {lre_api_key}"
    }

    response = requests.get(
        f"{lre_host}/loadtest/rest/domains",
        headers=headers,
        verify=False,
        timeout=60
    )

    results.append(f"LRE Status Code: {response.status_code}")
    results.append(f"LRE Response Size: {len(response.text)}")

except Exception as e:
    results.append(f"LRE Exception: {str(e)}")

# -------------------------
# Write Summary
# -------------------------

output_dir = Path("analysis_output")
output_dir.mkdir(exist_ok=True)

summary = "# Connectivity Test Results\n\n"

for item in results:
    summary += f"- {item}\n"

(output_dir / "summary.md").write_text(summary)

print(summary)
