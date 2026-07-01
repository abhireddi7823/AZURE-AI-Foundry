from pathlib import Path
import requests
import urllib3
import socket

urllib3.disable_warnings()

output_dir = Path("analysis_output")
output_dir.mkdir(exist_ok=True)

results = []

results.append("# LRE Connectivity Report")
results.append("")

# =====================================================
# DNS TEST
# =====================================================

try:
    ip = socket.gethostbyname("lre.edb.com")
    results.append(f"DNS Resolution: SUCCESS")
    results.append(f"Resolved IP: {ip}")
except Exception as e:
    results.append(f"DNS Resolution Failed: {e}")

results.append("")

# =====================================================
# HOME PAGE TEST
# =====================================================

try:
    r = requests.get(
        "https://lre.edb.com",
        timeout=20,
        verify=False
    )

    results.append(f"Homepage Status Code: {r.status_code}")
    results.append(f"Homepage URL: {r.url}")

except Exception as e:
    results.append(f"Homepage Exception: {e}")

results.append("")

# =====================================================
# LRE UI TEST
# =====================================================

try:
    r = requests.get(
        "https://lre.edb.com/Loadtest/pcx/app/",
        timeout=20,
        verify=False
    )

    results.append(f"LRE UI Status Code: {r.status_code}")
    results.append(f"LRE UI URL: {r.url}")

except Exception as e:
    results.append(f"LRE UI Exception: {e}")

results.append("")

# =====================================================
# REST API TEST
# =====================================================

try:
    r = requests.get(
        "https://lre.edb.com/loadtest/rest/domains",
        timeout=20,
        verify=False
    )

    results.append(f"REST API Status Code: {r.status_code}")
    results.append(f"REST API Response Length: {len(r.text)}")

except Exception as e:
    results.append(f"REST API Exception: {e}")

results.append("")

# =====================================================
# SAVE REPORT
# =====================================================

summary = "\n".join(results)

with open("analysis_output/summary.md", "w", encoding="utf-8") as f:
    f.write(summary)

print(summary)
