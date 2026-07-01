import json
import os
from pathlib import Path

import requests

API_KEY = os.environ["AZURE_FOUNDRY_API_KEY"]
ENDPOINT = os.environ["AZURE_FOUNDRY_ENDPOINT"]
DEPLOYMENT = os.environ["AZURE_FOUNDRY_DEPLOYMENT"]
RUN_ID = os.environ["RUN_ID"]

OUTPUT_DIR = Path("analysis_output")
OUTPUT_DIR.mkdir(exist_ok=True)

prompt = f"""
Analyse LoadRunner Enterprise test run.

Run ID: {RUN_ID}

Provide:

1. Executive Summary
2. Performance Findings
3. SLA Assessment
4. Bottlenecks
5. Recommendations
   """

headers = {
"api-key": API_KEY,
"Content-Type": "application/json"
}

body = {
"model": DEPLOYMENT,
"messages": [
{
"role": "system",
"content": "You are a senior performance engineer."
},
{
"role": "user",
"content": prompt
}
],
"temperature": 0.2
}

response = requests.post(
f"{ENDPOINT}/chat/completions",
headers=headers,
json=body,
timeout=120
)

response.raise_for_status()

analysis = response.json()["choices"][0]["message"]["content"]

(Path("analysis_output") / "summary.md").write_text(
analysis,
encoding="utf-8"
)

(Path("analysis_output") / "summary.json").write_text(
json.dumps(
{"run_id": RUN_ID, "analysis": analysis},
indent=2
),
encoding="utf-8"
)

print("Analysis completed successfully")
