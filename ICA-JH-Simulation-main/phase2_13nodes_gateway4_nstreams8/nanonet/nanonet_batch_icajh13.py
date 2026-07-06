#!/usr/bin/env python3
"""
Phase 2 batch runner: icajh_srv6 vs baseline_ecmp (13-node gateway4 nstreams8).

Run as:
    sudo env ICA_REPETITIONS=5 python3 nanonet_batch_icajh13.py
Output: batch_result_icajh13.csv
"""

import subprocess, json, time, os, csv, sys, glob, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR   = os.path.join(SCRIPT_DIR, "..", "json")

TESTFILES = [
    "ICAWeights13.topo.sh",
    "ICAJH13.topo.sh",
]

# Human-readable experiment names written to CSV / flow archive filenames
EXP_NAME = {
    "ICAJH13.topo.sh":      "icajh_srv6",
    "ICAWeights13.topo.sh": "baseline_ecmp",
}

JSON_FILES = {
    "ICAJH13.topo.sh":      "icajh13_gateway4.json",
    "ICAWeights13.topo.sh": "icaweights13_gateway4.json",
}

# Nodes whose throughput.json is collected (core + source nodes)
TESTNODES = list(range(0, 5)) + [11, 12, 13, 14]

TIME              = 120
AT_START_DELAY    = 120
COMPLETION_MARGIN = 60
DEMAND_FACTOR     = 10000
BYTES_TO_KBITS    = 125

REPETITIONS = int(os.environ.get("ICA_REPETITIONS", os.environ.get("ICAJH13_REPETITIONS", "10")))

SLEEP_BETWEEN_TESTS = AT_START_DELAY + TIME + COMPLETION_MARGIN

# Gateway-facing interface at each core node (interface that connects directly to gateway 4)
GATEWAY_IFACES = {0: "0-1", 1: "1-2", 2: "2-2", 3: "3-1"}
# Source-facing interface at each source node (interface connecting source to node 0)
SOURCE_IFACES  = {11: "11-0", 12: "12-0", 13: "13-0", 14: "14-0"}

# Regex to extract the nuttcp final summary line: "1500.00 MB / 120.00 sec = 100.00 Mbps"
NUTTCP_RE = re.compile(r"(\d+\.?\d*)\s+MB\s*/\s*(\d+\.?\d*)\s+sec\s*=\s*(\d+\.?\d*)\s+Mbps")


def run(cmd, check=True, cwd=None):
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True,
                          cwd=cwd or SCRIPT_DIR)


def cleanup_run():
    run("atq | awk '{print $1}' | xargs -r atrm", check=False)
    run("pkill -f 'nuttcp.*R10000'", check=False)
    # flow_*.txt intentionally NOT deleted so logs survive for debugging
    run(f"rm -f {SCRIPT_DIR}/*.throughput.json", check=False)
    time.sleep(2)


def archive_flow_logs(exp_name, rep_n):
    """
    Archive flow_*.txt files immediately after each run.

    Naming: flow_{src}-{dst}.txt.{exp_name}.rep{rep_n}
    Only renames bare flow_*.txt files (not already-archived ones).
    Called AFTER data collection so the last repetition is also archived.
    """
    for path in glob.glob(os.path.join(SCRIPT_DIR, "flow_*.txt")):
        basename = os.path.basename(path)
        if basename.count(".") > 1:
            continue  # already archived — skip
        dest = f"{path}.{exp_name}.rep{rep_n}"
        try:
            os.rename(path, dest)
        except OSError:
            pass


def stop_topo(sh_path):
    run(f"bash {sh_path} --stop", check=False)
    time.sleep(5)
    cleanup_run()


def start_topo(sh_path):
    run(f"bash {sh_path}")


def collect_throughput(node):
    """Return (recv_bytes, sent_bytes, iface_tx_delta) from node's throughput.json."""
    tf = os.path.join(SCRIPT_DIR, f"{node}.throughput.json")
    result = run(f"ip netns exec {node} cat {tf}", check=False)
    if result.returncode != 0:
        return None, None, {}
    try:
        data = json.loads(result.stdout)
        return data.get("recv_bytes"), data.get("sent_bytes"), data.get("iface_tx_delta", {})
    except Exception:
        return None, None, {}


def parse_flow_mbps(flow_file):
    """Return (mbps, duration_sec) from the last nuttcp summary line, or (None, None)."""
    try:
        with open(flow_file) as fh:
            content = fh.read()
        last = None
        for m in NUTTCP_RE.finditer(content):
            last = m
        if last:
            return float(last.group(3)), float(last.group(2))
    except OSError:
        pass
    return None, None


def compute_mlu(sent_bytes_per_node, iface_tx_per_node, json_path):
    """Compute measured MLU using direct per-interface byte counters.

    Reads iface_tx_delta[node][iface] — the tx_bytes delta on each specific interface
    since the throughput daemon started.  This directly measures traffic on each directed
    link without relying on node-total conservation, which breaks for ICA-JH because
    SRv6 multi-hop paths cause each core node to forward bytes on multiple outbound
    interfaces simultaneously.

    Returns (measured_mlu, json_expected_mlu, link_utils_dict).
    """
    with open(json_path) as f:
        topology = json.load(f)

    link_cap = {(lk["i"], lk["j"]): lk["capacity"] for lk in topology["links"]}
    json_mlu = max(lk["utilization"] for lk in topology["links"])

    def link_util(traffic_bytes, link):
        if not traffic_bytes or traffic_bytes <= 0:
            return 0.0
        cap = link_cap.get(link, 1) * DEMAND_FACTOR * BYTES_TO_KBITS * 8
        return (traffic_bytes * 8 / TIME) / cap

    utils = []
    link_utils = {}

    # Source link utilizations: tx_bytes on each source's outbound interface toward node 0
    for n, iface in SOURCE_IFACES.items():
        tx = iface_tx_per_node.get(n, {}).get(iface, 0) or 0
        u = link_util(tx, (n, 0))
        utils.append(u)
        link_utils[(n, 0)] = (iface, tx, u)

    # Gateway link utilizations: tx_bytes on each core node's interface toward gateway 4
    for k, iface in GATEWAY_IFACES.items():
        if (k, 4) not in link_cap:
            continue
        tx = iface_tx_per_node.get(k, {}).get(iface, 0) or 0
        u = link_util(tx, (k, 4))
        utils.append(u)
        link_utils[(k, 4)] = (iface, tx, u)

    if not utils:
        return 0.0, json_mlu, {}

    return max(utils), json_mlu, link_utils


def run_experiment(sh_name, rep, total_reps):
    sh_path   = os.path.join(SCRIPT_DIR, sh_name)
    json_path = os.path.join(JSON_DIR, JSON_FILES[sh_name])
    exp_name  = EXP_NAME[sh_name]
    rep_n     = rep + 1  # 1-indexed

    print(f"\n  [RUN {rep_n}/{total_reps}]  experiment={exp_name}  topo={sh_name}")
    stop_topo(sh_path)
    cleanup_run()
    start_topo(sh_path)

    print(f"  Traffic TIME={TIME}s; waiting {SLEEP_BETWEEN_TESTS}s (delay+run+margin)...")
    time.sleep(SLEEP_BETWEEN_TESTS)

    recv_bytes = {}
    sent_bytes = {}
    iface_tx   = {}
    for node in TESTNODES:
        rb, sb, itx = collect_throughput(node)
        recv_bytes[node] = rb
        sent_bytes[node] = sb
        iface_tx[node]   = itx

    # Parse nuttcp flow logs for throughput summary
    flow_pairs = [("11", "21"), ("12", "22"), ("13", "23"), ("14", "24")]
    total_mbps = 0.0
    print("  Flows:")
    for src, dst in flow_pairs:
        flow_file = os.path.join(SCRIPT_DIR, f"flow_{src}-{dst}.txt")
        mbps, dur = parse_flow_mbps(flow_file)
        if mbps is not None:
            total_mbps += mbps
        mbps_str = f"{mbps:.2f} Mbps" if mbps is not None else "N/A"
        dur_str  = f"{dur:.1f}s"       if dur  is not None else "?"
        print(f"    {src}→{dst}: {mbps_str} ({dur_str})")
    print(f"  Total: {total_mbps:.2f} Mbps")

    measured_mlu, json_mlu, link_utils = compute_mlu(sent_bytes, iface_tx, json_path)

    print("  Link utilizations (direct per-interface measurement):")
    for k, iface in GATEWAY_IFACES.items():
        if (k, 4) in link_utils:
            lif, tx, u = link_utils[(k, 4)]
            print(f"    ({k}→4) iface={lif} tx_delta={tx} util={u:.4f}")
    print(f"  measured_mlu={measured_mlu:.4f}  json_expected_mlu={json_mlu:.4f}")

    # Node counters for debugging
    ctr_parts = [f"n{n}:s={sent_bytes.get(n)} r={recv_bytes.get(n)}" for n in TESTNODES]
    print(f"  Node counters: {' | '.join(ctr_parts)}")

    # Diagnostic: print flow log tails for error visibility
    for flow_file in sorted(glob.glob(os.path.join(SCRIPT_DIR, "flow_*.txt"))):
        fname = os.path.basename(flow_file)
        try:
            with open(flow_file) as fh:
                content = fh.read().strip()
            last = "\n    ".join(content.splitlines()[-5:]) if content else "(empty)"
            print(f"  --- {fname} (last 5 lines) ---\n    {last}")
        except OSError as exc:
            print(f"  --- {fname}: could not read ({exc})")

    # Archive flow logs AFTER data collection; archives the last rep too
    archive_flow_logs(exp_name, rep_n)
    stop_topo(sh_path)

    return recv_bytes, sent_bytes, measured_mlu, json_mlu


def purge_bare_flow_logs():
    """Delete bare flow_*.txt files before the batch starts.

    Only removes unarchived logs (flow_*.txt with no extra dots in the name).
    Archived logs (flow_*.txt.baseline_ecmp.rep<N>, flow_*.txt.icajh_srv6.rep<N>)
    are never touched.
    """
    for path in glob.glob(os.path.join(SCRIPT_DIR, "flow_*.txt")):
        basename = os.path.basename(path)
        if basename.count(".") == 1:  # bare: exactly one dot → "flow_X-Y.txt"
            try:
                os.remove(path)
            except OSError:
                pass


def main():
    if os.geteuid() != 0:
        print("ERROR: must run as root (sudo python3 nanonet_batch_icajh13.py)", file=sys.stderr)
        sys.exit(1)

    purge_bare_flow_logs()

    out_csv = os.path.join(SCRIPT_DIR, "batch_result_icajh13.csv")
    rows = []

    for sh_name in TESTFILES:
        exp_name = EXP_NAME[sh_name]
        print(f"\n=== {sh_name} → {exp_name} ({REPETITIONS} repetitions) ===")
        for rep in range(REPETITIONS):
            recv_bytes, sent_bytes, measured_mlu, json_mlu = run_experiment(sh_name, rep, REPETITIONS)
            row = {
                "experiment":       exp_name,
                "repetition":       rep + 1,
                "measured_mlu":     round(measured_mlu, 6),
                "json_expected_mlu": round(json_mlu, 6),
            }
            for node in TESTNODES:
                row[f"recv_bytes_node{node}"] = recv_bytes.get(node)
                row[f"sent_bytes_node{node}"] = sent_bytes.get(node)
            rows.append(row)

    fieldnames = ["experiment", "repetition", "measured_mlu", "json_expected_mlu"] + \
                 [f"recv_bytes_node{n}" for n in TESTNODES] + \
                 [f"sent_bytes_node{n}" for n in TESTNODES]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults written to {out_csv}")


if __name__ == "__main__":
    main()
