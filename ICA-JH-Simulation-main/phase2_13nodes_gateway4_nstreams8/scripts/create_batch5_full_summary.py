#!/usr/bin/env python3
"""
Create full summary from all available batch run outputs.

Reads (all optional — writes null when missing):
  nanonet/batch_result_icajh13.csv          per-run node byte counters + measured_mlu
  nanonet/flow_<src>-<dst>.txt.<exp>.rep<N> nuttcp logs archived by the batch runner
                                            (archived immediately after each run;
                                             naming: flow_{src}-{dst}.txt.{exp}.rep{N}
                                             where exp = "icajh_srv6" or "baseline_ecmp"
                                             and N = 1-indexed repetition number)
  json/icajh13_gateway4.json                json_expected_mlu for ICA-JH experiment
  json/icaweights13_gateway4.json           json_expected_mlu for ECMP baseline

Writes:
  results/batch5_full_summary.csv
  results/batch5_full_summary.json

Run from any directory — uses __file__ for all paths:
  python3 scripts/create_batch5_full_summary.py
"""

import csv
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR   = Path(__file__).parent
PROJECT_DIR  = SCRIPT_DIR.parent
NANONET_DIR  = PROJECT_DIR / "nanonet"
JSON_DIR     = PROJECT_DIR / "json"
RESULTS_DIR  = PROJECT_DIR / "results"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JSON_FILES = {
    "icajh_srv6":    "icajh13_gateway4.json",
    "baseline_ecmp": "icaweights13_gateway4.json",
}

JSON_EXPECTED_MLU = {
    "icajh_srv6":    1.0,
    "baseline_ecmp": 2.0,
}

TOPO_FILE = {
    "icajh_srv6":    "ICAJH13.topo.sh",
    "baseline_ecmp": "ICAWeights13.topo.sh",
}

FLOWS = [("11", "21"), ("12", "22"), ("13", "23"), ("14", "24")]
CORE_NODES = [0, 1, 2, 3, 4, 11, 12, 13, 14]

# Matches: "1500.0000 MB / 120.00 sec = 1059.3000 Mbps ..."
NUTTCP_RE = re.compile(
    r"(\d+\.?\d*)\s+MB\s*/\s*(\d+\.?\d*)\s+sec\s*=\s*(\d+\.?\d*)\s+Mbps"
)

# Fatal errors → flow invalid regardless of any earlier success
FATAL_PATTERNS = [
    "connect failed",
    "Connection timed out",
    "refused",
    "reset by peer",
    "No route to host",
    "Network is unreachable",
    "Cannot open network namespace",
]

# Non-fatal — keep valid=True but record as warning
NONFATAL_PATTERNS = [
    "timeout while draining socket send queue",
    "Bad file descriptor",
]

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json_expected_mlu(exp_key: str) -> float:
    """Read max utilization from experiment JSON; fall back to hardcoded default."""
    fname = JSON_FILES.get(exp_key)
    if fname:
        jpath = JSON_DIR / fname
        try:
            with open(jpath) as f:
                data = json.load(f)
            return max(lk["utilization"] for lk in data["links"])
        except Exception:
            pass
    return JSON_EXPECTED_MLU.get(exp_key, 0.0)

# ---------------------------------------------------------------------------
# nuttcp flow-file parsing
# ---------------------------------------------------------------------------

def parse_flow_file(path):  # type: (Optional[str]) -> dict
    """
    Parse a nuttcp flow log file.

    Returns dict with:
      mbps          float | None   — from last nuttcp summary line
      duration_sec  float | None   — test duration from last summary
      mb_total      float | None   — total MB from last summary
      valid         bool | None    — True if success, False if fatal error, None if unknown
      warning       str  | None    — non-fatal warning text
    """
    result = dict(mbps=None, duration_sec=None, mb_total=None, valid=None, warning=None)

    if not path or not os.path.exists(path):
        return result

    try:
        with open(path, errors="replace") as f:
            content = f.read()
    except OSError as exc:
        result["valid"] = False
        result["warning"] = f"cannot read: {exc}"
        return result

    # Locate last nuttcp summary line
    last_match = None
    for m in NUTTCP_RE.finditer(content):
        last_match = m

    if last_match:
        result["mb_total"]    = float(last_match.group(1))
        result["duration_sec"] = float(last_match.group(2))
        result["mbps"]        = float(last_match.group(3))

        # Check for fatal errors AFTER the last summary (indicates final attempt failed)
        tail = content[last_match.end():]
        for pat in FATAL_PATTERNS:
            if pat in tail:
                result["valid"]   = False
                result["warning"] = f"fatal error after last summary: {pat}"
                return result

        result["valid"] = True
        for pat in NONFATAL_PATTERNS:
            if pat in content:
                result["warning"] = pat
                break

    else:
        # No summary line — check for fatal errors anywhere in file
        for pat in FATAL_PATTERNS:
            if pat in content:
                result["valid"]   = False
                result["warning"] = pat
                return result
        result["valid"]   = None
        result["warning"] = "no nuttcp summary line found"

    return result


def find_flow_file(exp, rep, src, dst):  # type: (str, int, str, str) -> Optional[str]
    """
    Locate the nuttcp log for a specific experiment / repetition / flow pair.

    Archive naming (set by nanonet_batch_icajh13.py archive_flow_logs):
      flow_{src}-{dst}.txt.{exp}.rep{rep}   — archived immediately after each run

    All repetitions including the last are archived, so no live-file fallback needed.
    exp = "icajh_srv6" or "baseline_ecmp" (matches EXP_NAME in batch runner).
    rep = 1-indexed repetition number (from the CSV "repetition" column).
    """
    base = f"flow_{src}-{dst}.txt"
    archived = NANONET_DIR / f"{base}.{exp}.rep{rep}"
    if archived.exists():
        return str(archived)
    return None

# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_batch_csv():  # type: () -> List[dict]
    csv_path = NANONET_DIR / "batch_result_icajh13.csv"
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows

# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def build_summary_row(csv_row):  # type: (dict) -> dict
    exp = csv_row.get("experiment", "")
    rep = int(csv_row.get("repetition", 1))

    row = {
        "run_id":            f"{exp}_rep{rep:02d}",
        "experiment":        exp,
        "topology_file":     TOPO_FILE.get(exp, ""),
        "valid":             None,
        "total_mbps":        None,
        "json_expected_mlu": load_json_expected_mlu(exp),
        "measured_mlu":      None,
    }

    # Measured MLU from batch CSV (computed purely from node byte counters)
    try:
        row["measured_mlu"] = float(csv_row["measured_mlu"])
    except (KeyError, TypeError, ValueError):
        pass

    # Per-flow data from nuttcp logs
    flow_mbps_list = []  # type: List[float]
    flow_valids    = []  # type: List[Optional[bool]]

    for src, dst in FLOWS:
        fkey   = f"flow_{src}_{dst}"
        fpath  = find_flow_file(exp, rep, src, dst)
        parsed = parse_flow_file(fpath)

        row[f"{fkey}_mbps"]     = parsed["mbps"]
        row[f"{fkey}_duration"] = parsed["duration_sec"]
        flow_valids.append(parsed["valid"])
        if parsed["mbps"] is not None:
            flow_mbps_list.append(parsed["mbps"])

    # Run is valid only when all 4 flows completed successfully
    if all(v is True for v in flow_valids):
        row["valid"] = True
    elif any(v is False for v in flow_valids):
        row["valid"] = False
    # else: None — files missing; cannot determine

    row["total_mbps"] = round(sum(flow_mbps_list), 4) if flow_mbps_list else None

    # Node byte counters from batch CSV
    for n in CORE_NODES:
        for out_field, csv_field in (
            (f"node_{n}_recv_bytes", f"recv_bytes_node{n}"),
            (f"node_{n}_tx_bytes",   f"sent_bytes_node{n}"),
        ):
            val = csv_row.get(csv_field)
            try:
                row[out_field] = int(float(val)) if val not in (None, "", "None") else None
            except (TypeError, ValueError):
                row[out_field] = None

    return row

# ---------------------------------------------------------------------------
# Field ordering
# ---------------------------------------------------------------------------

FIELDNAMES = (
    ["run_id", "experiment", "topology_file", "valid", "total_mbps"]
    + [f"flow_{s}_{d}_mbps"     for s, d in FLOWS]
    + [f"flow_{s}_{d}_duration" for s, d in FLOWS]
    + ["measured_mlu", "json_expected_mlu"]
    + [f"node_{n}_{f}" for n in CORE_NODES for f in ("recv_bytes", "tx_bytes")]
)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_rows = load_batch_csv()
    if not csv_rows:
        print(
            f"WARNING: {NANONET_DIR / 'batch_result_icajh13.csv'} not found or empty.\n"
            "         Run the batch experiment on Linux first, then re-run this script.\n"
            "         Writing empty summary files."
        )

    summary_rows = [build_summary_row(r) for r in csv_rows]

    out_csv  = RESULTS_DIR / "batch5_full_summary.csv"
    out_json = RESULTS_DIR / "batch5_full_summary.json"

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(out_json, "w") as f:
        json.dump(summary_rows, f, indent=2, default=str)

    total  = len(summary_rows)
    valid  = sum(1 for r in summary_rows if r.get("valid") is True)
    print(f"Wrote {total} rows  ({valid} valid)")
    print(f"  {out_csv}")
    print(f"  {out_json}")


if __name__ == "__main__":
    main()
