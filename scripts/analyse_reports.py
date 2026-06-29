#!/usr/bin/env python3
"""
analyse_reports.py
──────────────────
Reads LRE HTML report, Trend report, and SLA status then calls
Azure AI Foundry (primary → secondary fallback) to produce a
structured performance analysis.

Inputs (via environment variables set by the workflow)
──────────────────────────────────────────────────────
  AZURE_FOUNDRY_API_KEY        Azure AI Foundry API key
  PRIMARY_DEPLOYMENT           e.g. gpt-4o
  SECONDARY_DEPLOYMENT         e.g. gpt-4o-mini
  SLA_STATUS                   Passed | Failed (from SLA.xml)
  RUN_ID                       LRE Run ID
  HTML_REPORT_DIR              Directory containing unzipped HTML report
  TREND_REPORT_DIR             Directory containing unzipped Trend report
  GITHUB_RUN_NUMBER            GitHub Actions run number

Outputs
──────────────────────────────────────────────────────
  analysis_output/summary.md   Full markdown report
  analysis_output/summary.json Machine-readable version
"""

import json
import os
import re
import textwrap
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────

API_KEY   = os.environ["AZURE_FOUNDRY_API_KEY"]
ENDPOINT  = "https://lre-performance-project-resource.services.ai.azure.com/openai/v1"
PRIMARY   = os.environ.get("PRIMARY_DEPLOYMENT",   "gpt-4o")
SECONDARY = os.environ.get("SECONDARY_DEPLOYMENT", "gpt-4o-mini")

SLA_STATUS       = os.environ.get("SLA_STATUS",        "Unknown")
LRE_RUN_ID       = os.environ.get("RUN_ID",            "unknown")
HTML_REPORT_DIR  = os.environ.get("HTML_REPORT_DIR",   "reports/html")
TREND_REPORT_DIR = os.environ.get("TREND_REPORT_DIR",  "reports/trend")
GH_RUN_NUMBER    = os.environ.get("GITHUB_RUN_NUMBER", "0")
REPO             = os.environ.get("GITHUB_REPOSITORY", "unknown/repo")
SERVER_URL       = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
GITHUB_RUN_ID    = os.environ.get("GITHUB_RUN_ID",     "0")

OUTPUT_DIR = Path("analysis_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHAT_URL = f"{ENDPOINT}/chat/completions"


# ── Helpers ──────────────────────────────────────────────────────────────────

def find_html_file(directory: str, exclude_keyword: str = "") -> str:
    """
    Return path of the first .html file found in directory.
    Optionally skip files containing exclude_keyword in their name.
    """
    base = Path(directory)
    if not base.exists():
        return ""
    for f in sorted(base.rglob("*.html")):
        if exclude_keyword and exclude_keyword.lower() in f.name.lower():
            continue
        return str(f)
    return ""


def find_trend_file(directory: str) -> str:
    """Return path of trend HTML file, preferring files with 'trend' in name."""
    base = Path(directory)
    if not base.exists():
        return ""
    # Prefer files with 'trend' in name
    for f in sorted(base.rglob("*.html")):
        if "trend" in f.name.lower():
            return str(f)
    # Fall back to any HTML in the trend dir
    for f in sorted(base.rglob("*.html")):
        return str(f)
    return ""


def extract_text_from_html(path: str, max_chars: int = 12_000) -> str:
    """Parse an HTML file and return visible text, truncated to max_chars."""
    if not path or not Path(path).exists():
        return ""
    raw = Path(path).read_text(errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "head", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def extract_sla_details_from_html(path: str) -> str:
    """
    Try to extract SLA-specific rows/sections from the HTML report
    to give the AI richer SLA context beyond the single Passed/Failed flag.
    """
    if not path or not Path(path).exists():
        return ""
    raw = Path(path).read_text(errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    sla_chunks = []
    # Look for tables or divs that mention SLA
    for tag in soup.find_all(True):
        text = tag.get_text(separator=" ", strip=True)
        if "sla" in text.lower() and len(text) < 2000:
            sla_chunks.append(text)
            if len(sla_chunks) >= 5:
                break
    return "\n\n".join(sla_chunks)[:3000]


def call_foundry(model: str, system: str, user: str) -> str:
    """POST a chat completion request to Azure AI Foundry."""
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
    }
    r = requests.post(CHAT_URL, headers=headers, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"].strip()


# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are a senior performance-engineering consultant reviewing a
    LoadRunner Enterprise (LRE) test execution.

    Analyse the provided data and produce a structured report with
    EXACTLY these sections using the headings shown:

    ## Executive Summary
    2–4 paragraphs covering: overall health, key metrics observed,
    whether SLAs were met, and the most critical finding.

    ## SLA Analysis
    A markdown table with columns:
    | SLA Rule | Threshold | Actual | Status |
    List every SLA rule found. If details are not available, summarise
    the overall SLA status (Passed/Failed) and explain what it means.

    ## Response Time Table
    A markdown table with columns:
    | Transaction | Samples | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Error % |
    Include all transactions found in the report.

    ## Slow Transactions
    Bullet list of transactions where p90 > 2000 ms or error rate > 1%.
    For each: state the p90 value and a short root-cause hypothesis.
    If none, write "No slow transactions detected."

    ## Errors
    List each unique error message, its count, and likely cause.
    If none, write "No errors detected."

    ## Trend Analysis
    Summarise run-over-run trends: is performance improving, degrading,
    or stable? Call out any metric that changed by more than 10% since
    the previous run. If trend data is not available, write "Trend data
    not available for this run."

    ## Conclusion & Recommendations
    Numbered list of actionable recommendations ordered by priority.

    Use professional, concise language. Use markdown formatting only.
""").strip()


# ── Core analysis ─────────────────────────────────────────────────────────────

def build_user_prompt(
    sla_status: str,
    html_text: str,
    sla_detail: str,
    trend_text: str,
    run_id: str,
) -> str:
    return textwrap.dedent(f"""
        ### Run Metadata
        - LRE Run ID     : {run_id}
        - Overall SLA    : {sla_status}
        - GitHub Run #   : {GH_RUN_NUMBER}

        ### SLA Detail (extracted from report)
        {sla_detail or "(not available)"}

        ### HTML Performance Report
        {html_text or "(not provided)"}

        ### Trend Report
        {trend_text or "(not provided)"}
    """).strip()


def analyse(prompt: str) -> dict:
    for model in (PRIMARY, SECONDARY):
        try:
            print(f"  → Calling Azure AI Foundry: {model}")
            content = call_foundry(model, SYSTEM_PROMPT, prompt)
            return {"model_used": model, "content": content}
        except Exception as exc:
            print(f"  ⚠  {model} failed: {exc}")
    raise RuntimeError("Both primary and secondary Azure AI Foundry models failed.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("LRE Performance Analyser")
    print("=" * 60)
    print(f"Endpoint        : {ENDPOINT}")
    print(f"Primary model   : {PRIMARY}")
    print(f"Secondary model : {SECONDARY}")
    print(f"LRE Run ID      : {LRE_RUN_ID}")
    print(f"SLA Status      : {SLA_STATUS}")
    print(f"HTML Report Dir : {HTML_REPORT_DIR}")
    print(f"Trend Report Dir: {TREND_REPORT_DIR}")
    print("=" * 60)

    # ── Locate report files ───────────────────────────────────────────────────
    html_file  = find_html_file(HTML_REPORT_DIR)
    trend_file = find_trend_file(TREND_REPORT_DIR)

    print(f"HTML file  → {html_file  or 'NOT FOUND'}")
    print(f"Trend file → {trend_file or 'NOT FOUND'}")

    # ── Extract content ───────────────────────────────────────────────────────
    html_text  = extract_text_from_html(html_file)
    sla_detail = extract_sla_details_from_html(html_file)
    trend_text = extract_text_from_html(trend_file, max_chars=6_000)

    if not html_text and not trend_text:
        print("⚠  No report content found – using placeholder.")
        html_text = (
            "No report content found. "
            "Ensure the HTML report was correctly downloaded and unzipped."
        )

    # ── Build prompt & call AI ────────────────────────────────────────────────
    prompt = build_user_prompt(
        sla_status=SLA_STATUS,
        html_text=html_text,
        sla_detail=sla_detail,
        trend_text=trend_text,
        run_id=LRE_RUN_ID,
    )

    result     = analyse(prompt)
    model_used = result["model_used"]
    markdown   = result["content"]

    # ── Prepend a metadata header to the markdown ─────────────────────────────
    run_url = f"{SERVER_URL}/{REPO}/actions/runs/{GITHUB_RUN_ID}"
    header = textwrap.dedent(f"""
        # LRE Performance Analysis – Run #{GH_RUN_NUMBER}

        | Field          | Value |
        |----------------|-------|
        | LRE Run ID     | `{LRE_RUN_ID}` |
        | SLA Status     | **{SLA_STATUS}** |
        | AI Model Used  | `{model_used}` |
        | GitHub Run     | [#{GH_RUN_NUMBER}]({run_url}) |

        ---

    """).lstrip()

    full_markdown = header + markdown

    # ── Write outputs ─────────────────────────────────────────────────────────
    md_path = OUTPUT_DIR / "summary.md"
    md_path.write_text(full_markdown, encoding="utf-8")
    print(f"\n✅  Markdown report  → {md_path}")

    summary_obj = {
        "lre_run_id":    LRE_RUN_ID,
        "sla_status":    SLA_STATUS,
        "model_used":    model_used,
        "github_run":    GH_RUN_NUMBER,
        "run_url":       run_url,
        "repo":          REPO,
        "html_report":   html_file,
        "trend_report":  trend_file,
        "markdown":      full_markdown,
    }
    json_path = OUTPUT_DIR / "summary.json"
    json_path.write_text(
        json.dumps(summary_obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅  JSON summary     → {json_path}")
    print(f"✅  Model used       : {model_used}")
    print("Done.")


if __name__ == "__main__":
    main()
