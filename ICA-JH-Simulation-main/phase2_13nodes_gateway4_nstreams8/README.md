# Phase 2: ICA-JH SRv6 vs ECMP Baseline — 13-Node Topology, Gateway 4

## Overview

This directory contains a complete Nanonet emulation comparing two traffic engineering strategies on a 13-node topology with gateway node 4 and 8 measurement streams per flow:

| Experiment | Folder | Routing | Expected MLU |
|------------|--------|---------|--------------|
| `baseline_ecmp` | `Baseline-ECMP/` | ECMP weights only, **no SRv6** | **2.0** |
| `icajh_srv6` | `ICA_JH_SRv6/` | ICA-JH algorithm with **SRv6 waypoints** | **1.0** |

The comparison is fair: both experiments use the same 13-node topology, the same four demands, the same link capacities, the same nuttcp traffic settings (TIME=120s, NSTREAMS=8, rate 10 Mbps/demand). **Only the routing mechanism differs.**

ICA-JH with SRv6 achieves a **50% MLU reduction** compared to the ECMP baseline by steering traffic through waypoint nodes, eliminating the congestion on link (0→4).

---

## Topology and Fair Comparison

```
Sources:   11  12  13  14
            \   |   |  /
             \  |  /  /
              node 0
             / |
            /  |             Core chain (tc 800 Mbps, JSON 8 units, cost 1000)
           0 - 1 - 2 - 3
           |   |   |   |
           +---+---+---+     Gateway links → node 4
                   |
                   4          Gateway node
                 / | \ \
               21  22  23  24   Receiver nodes
```

### Link capacities (same in both experiments)

All `tc htb` rates are set to 10× the maximum possible demand on each link so that
`tc` never acts as the bottleneck — the nuttcp rate limit (`-R10000` kbit/s = 10 Mbps)
is the only traffic constraint. MLU is computed from node byte counters and JSON
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
├── README.md                          This file
├── phase1_to_nanonet_icajh13_trace.py Algorithm trace + MLU assertions (stdlib only)
│
├── Baseline-ECMP/                     ECMP baseline reference
│   ├── ICAWeights13.topo.py           Nanonet Python topology (reference copy)
│   └── README.md                      Experiment documentation
│
├── ICA_JH_SRv6/                       ICA-JH SRv6 experiment reference
│   ├── ICAJH13.topo.py                Nanonet Python topology (reference copy)
│   └── README.md                      Experiment documentation
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
│   ├── run_batch5.sh                  Run 5+5 experiments on Linux (calls batch runner)
│   └── create_batch5_full_summary.py  Build full CSV+JSON summary from run outputs
│
├── results/                           [generated after Linux run + summary script]
│   ├── batch5_full_summary.csv
│   └── batch5_full_summary.json
│
└── Plots/                             [generated after Linux run]
    └── (PNG/PDF plots go here)
```

> **nanonet/ is runtime-critical.** The `.topo.sh` scripts, `nanonet_batch_icajh13.py`,
> and `throughput.py` must remain in `nanonet/` — the batch runner resolves all paths
> relative to its own directory. The topology files in `Baseline-ECMP/` and `ICA_JH_SRv6/`
> are reference copies only.

---

## Parameters

| Parameter | Value |
|-----------|-------|
| TIME (nuttcp duration) | 120 s |
| NSTREAMS (parallel streams) | 8 |
| Rate per stream | 10000 KB/s = 10 Mbps |
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
cd phase2_13nodes_gateway4_nstreams8/
python3 phase1_to_nanonet_icajh13_trace.py
# Expected output: "All assertions passed."  (Case 1 MLU=2.0, Case 2 MLU=1.0)
```

### 2. Run a single topology (Linux only)

```bash
cd phase2_13nodes_gateway4_nstreams8/nanonet/
sudo bash ICAWeights13.topo.sh     # ECMP baseline
sudo bash ICAJH13.topo.sh          # ICA-JH SRv6
# Tear down:
sudo bash ICAJH13.topo.sh --stop
```

### 3. Run the full batch experiment (Linux only)

```bash
cd phase2_13nodes_gateway4_nstreams8/
sudo bash scripts/run_batch5.sh 5      # 5 reps each experiment (~50 min total)
# Or override via env var:
sudo REPS=3 bash scripts/run_batch5.sh
# Or directly:
cd nanonet/
sudo env ICA_REPETITIONS=5 python3 nanonet_batch_icajh13.py
```

Output: `nanonet/batch_result_icajh13.csv`

### 4. Generate full summary (after Linux runs)

```bash
python3 scripts/create_batch5_full_summary.py
# Reads: nanonet/batch_result_icajh13.csv + nanonet/flow_*.txt logs
# Writes: results/batch5_full_summary.csv
#         results/batch5_full_summary.json
```

### 5. Generate boxplot

```bash
python3 nanonet/gen_boxplot_icajh13.py
# Reads:  nanonet/batch_result_icajh13.csv
# Writes: nanonet/icajh13_vs_icaweights13_boxplot.png
# Move to Plots/:
mv nanonet/icajh13_vs_icaweights13_boxplot.png Plots/
```

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

Measured MLU is computed from node-level byte counters written by `throughput.py`
(a daemon started inside each network namespace). No JSON utilization values are used.

Two types of link utilization are combined:
1. **Source link utilization** — each source node (11-14) sends only on its one uplink to node 0, so `sent_bytes / TIME / capacity` gives the link utilization directly.
2. **Gateway link utilization** — estimated from the chain conservation property: `traffic_on_(k→4) ≈ sent_bytes[k] − sent_bytes[k+1]` for core nodes k = 0, 1, 2, 3.

`measured_mlu = max(all computed link utilizations)`

For ICAWeights13 (ECMP): the (0→4) bottleneck carries ≈2×flow → measured_mlu ≈ 2.0.
For ICAJH13 (SRv6): all gateway and source links carry ≈1×flow at their capacity → measured_mlu ≈ 1.0.

---

## What Changed vs. Original Files

| Change | Scope | Reason |
|--------|-------|--------|
| Folder structure added (Baseline-ECMP, ICA_JH_SRv6, scripts, results, Plots) | Organization only | Clean self-contained project |
| `scripts/create_batch5_full_summary.py` | New file | Post-processing: full CSV+JSON summary |
| `scripts/run_batch5.sh` | New file | Convenience wrapper for batch runner |
| `nanonet/nanonet_batch_icajh13.py` | `compute_mlu()` only | Fixed MLU measurement: uses node byte counter differences instead of json_mlu scaling |
| `nanonet/ICAJH13.topo.sh` | Routes for node 24 | Added missing return routes so TCP SYN-ACKs reach source loopbacks |
| `nanonet/ICAWeights13.topo.sh` | Routes for nodes 21-24 | Added missing return routes for all receiver nodes |
| `README.md` | This file | Replaces README_phase2_13nodes.md |

**Not changed:** ICA-JH algorithm logic, waypoint assignments, topology capacities,
JSON files, TIME=120, NSTREAMS=8, or any file outside this directory.
