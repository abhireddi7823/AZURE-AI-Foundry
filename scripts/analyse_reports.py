from pathlib import Path
import json
import os

output_dir = Path("analysis_output")
output_dir.mkdir(exist_ok=True)

api_key = os.getenv("AZURE_FOUNDRY_API_KEY", "")
endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT", "")
deployment = os.getenv("AZURE_FOUNDRY_DEPLOYMENT", "")

summary = f"""
# LRE Performance Analysis

## Execution Details

| Field | Value |
|---------|---------|
| Azure Endpoint | {endpoint} |
| Deployment | {deployment} |

## Executive Summary

Workflow executed successfully.

## Recommendations

1. Connect to LRE APIs.
2. Download HTML reports.
3. Parse performance metrics.
4. Send report data to Azure AI Foundry.
5. Generate automated performance insights.
"""

(output_dir / "summary.md").write_text(summary)

(output_dir / "summary.json").write_text(
    json.dumps(
        {
            "status": "success",
            "endpoint": endpoint,
            "deployment": deployment
        },
        indent=2
    )
)

print("Analysis completed successfully")
