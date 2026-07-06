# Phase 2: ICA-JH SRv6 vs ECMP Baseline — 13-Node Topology, Gateway 4

## Overview

This directory contains a complete Nanonet emulation comparing two traffic engineering strategies on a 13-node topology with gateway node 4 and 8 measurement streams per flow:

| Experiment | Folder | Routing | Expected MLU |
|------------|--------|---------|--------------|
| `baseline_ecmp` | `phase2_13nodes_gateway4_nstreams8/Baseline-ECMP/` | ECMP weights only, **no SRv6** | **2.0** |
| `icajh_srv6` | `phase2_13nodes_gateway4_nstreams8/ICA_JH_SRv6/` | ICA-JH algorithm with **SRv6 waypoints** | **1.0** |

The comparison is fair: both experiments use the same 13-node topology, the same four demands, the same link capacities, the same nuttcp traffic settings (TIME=120s, NSTREAMS=8, rate 10 Mbps/demand). **Only the routing mechanism differs.**

ICA-JH with SRv6 achieves a **50% MLU reduction** compared to the ECMP baseline by steering traffic through waypoint nodes, eliminating the congestion on link (0→4).

---

## Topology and Fair Comparison

### Link capacities (same in both experiments)

All `tc htb` rates are set to 10× the maximum possible demand on each link so that
`tc` never acts as the bottleneck — the nuttcp rate limit (`-R10000` kbit/s = 10 Mbps)
is the only traffic constraint. MLU is computed from per-interface TX byte deltas and JSON
capacities, not from `tc` rates.

| Link(s) | tc rate | JSON capacity | Role |
|---------|---------|---------------|------|
| 0-1, 1-2, 2-3 (core) | 800 Mbps | 8 units | non-bottleneck backbone |
| 0→4 | 100 Mbps | 1 unit | bottleneck for ECMP (MLU=2.0) |
| 1→4 | 200 Mbps | 2 units | absorbs 2 flows in ICA-JH |
| 2→4, 3→4 | 100 Mbps | 1 unit | gateway ingress |
| 1x→0 (source) | 100 Mbps | 1 unit | per-demand ingress |
| 4→2x (receiver) | 10 Gbps | — | never bottleneck |

1 JSON capacity unit = 1 nuttcp demand = 10 Mbps (`-R10000` kbit/s).

### Why ECMP creates congestion (MLU=2.0)

ICAWeights13 uses OSPF weights: w(0→4)=2 (cost 2000) and w(1→4)=1 (cost 1000).
- Path 0→4 direct: OSPF cost = 2000
- Path 0→1→4: OSPF cost = 1000 + 1000 = 2000

Both paths have equal cost → ECMP splits traffic 2/2. Link (0→4) carries 2 demands × 10 Mbps = 20 Mbps on a 10 Mbps link → **utilization = 2.0**.

### How ICA-JH with SRv6 fixes it (MLU=1.0)

ICAJH13 uses HeurOSPF weights (all gateway links cost=4000) and assigns SRv6 waypoints:

| Demand | Waypoint | Path | Link loaded |
|--------|----------|------|-------------|
| 11 → 21 | node 1 | 11→0→**1**→4→21 | (1→4): cap 2 |
| 12 → 22 | node 1 | 12→0→**1**→4→22 | (1→4): cap 2 |
| 13 → 23 | node 2 | 13→0→1→**2**→4→23 | (2→4): cap 1 |
| 14 → 24 | direct | 14→0→4→24 | (0→4): cap 1 |

Each link carries exactly one demand unit at its full capacity → all utilizations = 1.0 → **MLU = 1.0**.

---

## Folder Structure

```
phase2_13nodes_gateway4_nstreams8/
├── phase1_to_nanonet_icajh13_trace.py Algorithm trace + MLU assertions (stdlib only)
│
├── Baseline-ECMP/                     ECMP baseline reference
│   └── ICAWeights13.topo.py           Nanonet Python topology (reference copy)
│
├── ICA_JH_SRv6/                       ICA-JH SRv6 experiment reference
│   └── ICAJH13.topo.py                Nanonet Python topology (reference copy)
│
├── nanonet/                           RUNTIME-CRITICAL — do not move files here
│   ├── ICAJH13.topo.sh                Shell script: ICA-JH topology (executed on Linux)
│   ├── ICAJH13.topo.py                Nanonet Python source
│   ├── ICAWeights13.topo.sh           Shell script: ECMP topology (executed on Linux)
│   ├── ICAWeights13.topo.py           Nanonet Python source
│   ├── nanonet_batch_icajh13.py       Batch runner (both experiments, N repetitions)
│   ├── throughput.py                  Per-namespace byte-counter daemon
│   ├── gen_boxplot_icajh13.py         Boxplot generator (reads batch CSV)
│   └── batch_result_icajh13.csv       [generated after Linux run]
│
├── json/                              Input / expected-result files
│   ├── icajh13_gateway4.json          ICA-JH result: waypoints, link utils, MLU=1.0
│   └── icaweights13_gateway4.json     ECMP result: link utils, MLU=2.0
│
├── scripts/                           Analysis and automation scripts
│   ├── run_batch5.sh                  Run experiments on Linux (calls batch runner)
│   └── create_batch5_full_summary.py  Build full CSV+JSON summary from run outputs
│
├── results/                           Generated summaries and archived runs
│   ├── batch5_full_summary.csv        Historical batch summary (batch5 scripts)
│   ├── batch5_full_summary.json
│   ├── run10_full_summary.csv         Final 10-run full summary
│   ├── run10_full_summary.json
│   ├── run10_summary_table.csv        Final 10-run aggregate statistics
│   ├── run10_per_run_table.csv        Final 10-run per-repetition detail
│   └── run_1_test/                    Archived sanity-check run
│
└── Plots/                             Generated plots
    ├── run10_mlu_boxplot.png          MLU comparison boxplot (10 runs)
    └── run10_throughput_boxplot.png   Throughput comparison boxplot (10 runs)
```

> **`phase2_13nodes_gateway4_nstreams8/nanonet/` is runtime-critical.** The `.topo.sh` scripts, `nanonet_batch_icajh13.py`,
> and `throughput.py` must remain in `phase2_13nodes_gateway4_nstreams8/nanonet/` — the batch runner resolves all paths
> relative to its own directory. The topology files in `phase2_13nodes_gateway4_nstreams8/Baseline-ECMP/` and `phase2_13nodes_gateway4_nstreams8/ICA_JH_SRv6/`
> are reference copies only.

---

## Parameters

| Parameter | Value |
|-----------|-------|
| TIME (nuttcp duration) | 120 s |
| NSTREAMS (parallel streams) | 8 |
| nuttcp rate | -R10000 kbit/s = 10 Mbps per demand/flow |
| Default repetitions | 5 (override with `REPS=N`) |
| ICA-JH β | 0.9 |
| ICA-JH max_iterations | 10 |
| ICA-JH tie-breaker | WAPL (Weighted Average Path Length) |

---

## How to Run on Linux

### Prerequisites

```bash
which nuttcp at python3 ip tc   # all must be on PATH
sudo systemctl enable --now atd  # atd must be running
```

### 1. Verify the algorithm (Mac or Linux, no root needed)

Runs the ICA-JH trace in pure Python (stdlib only) and asserts both expected MLU values:

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8
python3 phase1_to_nanonet_icajh13_trace.py
# Expected output: "All assertions passed."  (Case 1 MLU=2.0, Case 2 MLU=1.0)
```

### 2. Run a single topology (Linux only)

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8/nanonet
sudo bash ICAWeights13.topo.sh     # ECMP baseline
sudo bash ICAJH13.topo.sh          # ICA-JH SRv6
# Tear down:
sudo bash ICAJH13.topo.sh --stop
```

### 3. Run the full batch experiment (Linux only)

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8
sudo bash scripts/run_batch5.sh 5      # 5 reps each experiment (~50 min total)
# Or override via env var:
sudo REPS=3 bash scripts/run_batch5.sh
# Or directly:
cd nanonet/
sudo env ICA_REPETITIONS=5 python3 nanonet_batch_icajh13.py
```

Output: `phase2_13nodes_gateway4_nstreams8/nanonet/batch_result_icajh13.csv`

### 4. Generate full summary (after Linux runs)

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8
python3 scripts/create_batch5_full_summary.py
# Reads: phase2_13nodes_gateway4_nstreams8/nanonet/batch_result_icajh13.csv + nanonet/flow_*.txt logs
# Writes: phase2_13nodes_gateway4_nstreams8/results/batch5_full_summary.csv
#         phase2_13nodes_gateway4_nstreams8/results/batch5_full_summary.json
```

### 5. Generate boxplots

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8
python3 nanonet/gen_boxplot_icajh13.py
# Reads:  phase2_13nodes_gateway4_nstreams8/nanonet/batch_result_icajh13.csv
# Writes: phase2_13nodes_gateway4_nstreams8/Plots/run10_mlu_boxplot.png
#         phase2_13nodes_gateway4_nstreams8/Plots/run10_throughput_boxplot.png
```

The final 10-run plots are already generated and stored in `phase2_13nodes_gateway4_nstreams8/Plots/`.

---

## Results

### Final 10-run experiment (Linux server)

Output files:

- `phase2_13nodes_gateway4_nstreams8/results/run10_full_summary.csv` — full per-run detail including parsed per-flow Mbps
- `phase2_13nodes_gateway4_nstreams8/results/run10_full_summary.json` — same data in JSON format
- `phase2_13nodes_gateway4_nstreams8/results/run10_summary_table.csv` — aggregate statistics (median, mean MLU and throughput)
- `phase2_13nodes_gateway4_nstreams8/results/run10_per_run_table.csv` — per-repetition MLU and throughput
- `phase2_13nodes_gateway4_nstreams8/Plots/run10_mlu_boxplot.png` — MLU comparison boxplot
- `phase2_13nodes_gateway4_nstreams8/Plots/run10_throughput_boxplot.png` — throughput comparison boxplot

Aggregate results (10 valid runs each):

| Experiment | Valid runs | Median MLU | Mean MLU | Expected MLU | Median Mbps | Mean Mbps |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `baseline_ecmp` | 10 | 2.0797 | 2.1188 | 2.0000 | 39.9967 | 39.9967 |
| `icajh_srv6` | 10 | 1.0124 | 1.0124 | 1.0000 | 39.9977 | 39.9977 |

Both variants consistently deliver the offered load (≈40 Mbps total). ICA-JH reduces median MLU from approximately 2.08 to approximately 1.01 — a roughly 51% reduction in bottleneck link concentration. Throughput is equivalent across both variants; the improvement is in load distribution, not aggregate throughput.

> `batch5_*` filenames in `phase2_13nodes_gateway4_nstreams8/results/` and `phase2_13nodes_gateway4_nstreams8/scripts/` are historical and retained for script compatibility. The `run10_*` files are the final reporting outputs.

### Sanity-check run (1 repetition)

Archived in `phase2_13nodes_gateway4_nstreams8/results/run_1_test/`. Used to verify correctness before the full batch:

| Variant | Total throughput | Measured MLU | Expected MLU |
|---|:---:|:---:|:---:|
| `baseline_ecmp` | ≈ 39.99 Mbps | 2.2704 | 2.0000 |
| `icajh_srv6` | ≈ 40.00 Mbps | 1.0124 | 1.0000 |

---

## Loopback Addresses

| Node | Loopback |
|------|----------|
| 0 | fc00:2:0:6::1 |
| 1 | fc00:2:0:2::1 |
| 2 | fc00:2:0:5::1 |
| 3 | fc00:2:0:3::1 |
| 4 | fc00:2:0:7::1 |
| 11 | fc00:2:0:1::1 |
| 12 | fc00:2:0:8::1 |
| 13 | fc00:2:0:4::1 |
| 14 | fc00:2:0:9::1 |
| 21 | fc00:2:0:a::1 |
| 22 | fc00:2:0:b::1 |
| 23 | fc00:2:0:c::1 |
| 24 | fc00:2:0:d::1 |

---

## MLU Measurement Method

`measured_mlu` is computed from direct per-interface TX byte deltas written by `throughput.py` (`iface_tx_delta`), running as a daemon inside each network namespace. JSON capacity values are used only as the denominator for normalization (reference MLU); they are not used as measured utilization.

Monitored interfaces:

| Role | Interface |
|---|---|
| Source uplinks (source→node 0) | `11-0`, `12-0`, `13-0`, `14-0` |
| Gateway-facing (node 0→4) | iface `0-1` on node 0 |
| Gateway-facing (node 1→4) | iface `1-2` on node 1 |
| Gateway-facing (node 2→4) | iface `2-2` on node 2 |
| Gateway-facing (node 3→4) | iface `3-1` on node 3 |

For each monitored interface:

```
link_util = (iface_tx_bytes × 8 / TIME) / (json_capacity × 10 Mbps)
measured_mlu = max(link_util over all source and gateway interfaces)
```

For `baseline_ecmp`: interface `0-1` (node 0→4, capacity 1 unit) carries ≈2 demands → `measured_mlu ≈ 2.0`.
For `icajh_srv6`: each gateway interface carries at most 1 demand at its capacity → `measured_mlu ≈ 1.0`.

---

## What Changed vs. Original Files

| Change | Scope | Reason |
|--------|-------|--------|
| Folder structure added (Baseline-ECMP, ICA_JH_SRv6, scripts, results, Plots) | Organization only | Clean self-contained project |
| `phase2_13nodes_gateway4_nstreams8/scripts/create_batch5_full_summary.py` | New file | Post-processing: full CSV+JSON summary |
| `phase2_13nodes_gateway4_nstreams8/scripts/run_batch5.sh` | New file | Convenience wrapper for batch runner |
| `phase2_13nodes_gateway4_nstreams8/nanonet/nanonet_batch_icajh13.py` | `compute_mlu()` only | Fixed MLU measurement: uses direct per-interface byte counters instead of the broken node-total conservation formula |
| `phase2_13nodes_gateway4_nstreams8/nanonet/ICAJH13.topo.sh` | Routes for node 24 | Added missing return routes so TCP SYN-ACKs reach source loopbacks |
| `phase2_13nodes_gateway4_nstreams8/nanonet/ICAWeights13.topo.sh` | Routes for nodes 21-24 | Added missing return routes for all receiver nodes |
| `README.md` | This file | Replaces README_phase2_13nodes.md |

**Not changed:** ICA-JH algorithm logic, waypoint assignments, topology capacities,
JSON files, TIME=120, NSTREAMS=8, or any file outside `phase2_13nodes_gateway4_nstreams8/`.
