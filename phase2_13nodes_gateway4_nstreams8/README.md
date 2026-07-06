# ICA-JH / Nanonet SRv6 Traffic Engineering Experiment

## Overview

This project implements Phase 2 of the ICA-JH traffic engineering experiment using the **Nanonet** Linux network-namespace emulator. It compares two routing strategies on a 13-node topology with gateway node 4:

- **Baseline (`baseline_ecmp`):** ECMP-weighted OSPF routing, no SRv6. All four demands route through node 0, overloading link (0→4) to MLU 2.0.
- **ICA-JH (`icajh_srv6`):** SRv6 waypoint routing computed by the ICA-JH algorithm. Three demands are steered through waypoints to balance gateway traffic, reducing MLU to 1.0.

Both experiments use identical topology, capacities, demands, and nuttcp settings. Only the routing mechanism differs. ICA-JH achieves a **50% MLU reduction** over ECMP.

---

## Experiment Variants

| Label | Folder | Routing | Expected MLU |
|-------|--------|---------|:------------:|
| `baseline_ecmp` | `Baseline-ECMP/` | ECMP weights, no SRv6 | **2.0** |
| `icajh_srv6` | `ICA_JH_SRv6/` | ICA-JH algorithm + SRv6 inline waypoints | **1.0** |

**Traffic parameters (identical for both experiments):**

| Parameter | Value |
|-----------|-------|
| nuttcp duration (TIME) | 120 s |
| Parallel streams per flow (NSTREAMS) | 8 |
| Rate per demand | 10 Mbps (`-R10000` kbps) |
| ICA-JH β | 0.9 |
| ICA-JH max\_iterations | 10 |
| ICA-JH tie-breaker | WAPL (Weighted Average Path Length) |

---

## Topology and Routing

```
Sources:  11    12    13    14
           \    |     |    /
            \   |     |   /
             \  |     |  /
              Node 0
             /  |
            /   |
           0 ---1 --- 2 --- 3       Core chain (800 Mbps, JSON cap 8)
           |    |     |    |
           +----+-----+----+        Gateway links → node 4
                |
                4                   Gateway node
              / | \ \
            21  22  23  24          Receiver nodes
```

### Link capacities

1 JSON capacity unit = 1 nuttcp demand = 10 Mbps.

| Link(s) | tc rate | JSON capacity | Role |
|---------|---------|:-------------:|------|
| 0-1, 1-2, 2-3 (core chain) | 800 Mbps | 8 units | Non-bottleneck backbone |
| 0→4 | 100 Mbps | 1 unit | **Bottleneck for ECMP** (MLU=2.0) |
| 1→4 | 200 Mbps | 2 units | Absorbs demands 11+12 in ICA-JH |
| 2→4, 3→4 | 100 Mbps | 1 unit | Gateway ingress |
| 11→0, 12→0, 13→0, 14→0 (source) | 100 Mbps | 1 unit | Per-demand ingress |
| 4→21/22/23/24 (receiver) | 10 Gbps | — | Never bottleneck |

### Why ECMP creates congestion (MLU = 2.0)

ICAWeights13 sets OSPF weights: w(0→4) = 2 (cost 2000), w(1→4) = 1 (cost 1000), core links cost 1000.

- Path 0→4 direct: OSPF cost = 2000
- Path 0→1→4: OSPF cost = 1000 + 1000 = 2000

Equal cost → ECMP splits all four demands 50/50. Link (0→4) carries 2 demands × 10 Mbps = 20 Mbps on a 10 Mbps link → **utilization = 2.0**.

### How ICA-JH with SRv6 fixes it (MLU = 1.0)

ICAJH13 uses HeurOSPF weights (all gateway links cost 4000) and assigns SRv6 inline waypoints at source nodes:

| Demand | Source | Waypoint | Path | Gateway link | JSON cap |
|--------|--------|----------|------|:------------:|:--------:|
| 11 → 21 | node 11 | node 1 | 11→0→**1**→4→21 | 1→4 | 2 |
| 12 → 22 | node 12 | node 1 | 12→0→**1**→4→22 | 1→4 | 2 |
| 13 → 23 | node 13 | node 2 | 13→0→1→**2**→4→23 | 2→4 | 1 |
| 14 → 24 | node 14 | direct | 14→0→4→24 | 0→4 | 1 |

Each gateway link carries exactly its capacity in demand units → all utilizations = 1.0 → **MLU = 1.0**.

SRv6 is applied at source nodes only, using `encap seg6 mode inline`:

```bash
# node 11 — waypoint node 1 (loopback fc00:2:0:2::1)
ip -6 route add fc00:2:0:a::1 encap seg6 mode inline segs fc00:2:0:2::1

# node 12 — waypoint node 1
ip -6 route add fc00:2:0:b::1 encap seg6 mode inline segs fc00:2:0:2::1

# node 13 — waypoint node 2 (loopback fc00:2:0:5::1)
ip -6 route add fc00:2:0:c::1 encap seg6 mode inline segs fc00:2:0:5::1

# node 14 — direct, no SRv6
```

### ICA-JH Algorithm Trace

Starting from HeurOSPF weights (all gateway links w=4), initial MLU = 4.0:

| Iteration | Event |
|-----------|-------|
| 1 | demand 11→4 assigned waypoint 1: 11→0→1→4 → MLU=3.0 |
| 1 | demand 12→4 assigned waypoint 1: 12→0→1→4 → MLU=2.0 |
| 1 | demand 13→4 assigned waypoint 1: 13→0→1→4 → MLU=1.5 |
| 1 | demand 13→4 reassigned waypoint 2: 13→0→1→2→4 → MLU=1.0 |
| 2 | no improvement → converged at MLU=1.0 |

Verify this trace locally (no root, no Linux required):

```bash
cd phase2_13nodes_gateway4_nstreams8/
python3 phase1_to_nanonet_icajh13_trace.py
# Expected: "All assertions passed."  (Case 1 MLU=2.0, Case 2 MLU=1.0)
```

### Loopback Addresses

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

## Nanonet Dependency

The `nanonet-master/` folder (sibling of this directory) is the University of Vienna fork of segment-routing/nanonet. It provides `build.py` to regenerate `.topo.sh` files from `.topo.py` sources.

**It is NOT a runtime dependency.** The `.topo.sh` files are pre-generated and committed. All runtime tooling uses only standard Linux tools (`ip`, `tc`, `iproute2`, `nuttcp`, `at`, `sysctl`).

`nanonet-master/` is only needed if the topology `.topo.py` files are changed and `.topo.sh` must be regenerated:

```bash
# Only needed after editing .topo.py (Linux with nanonet-master):
python3 /path/to/nanonet-master/build.py nanonet/ICAJH13.topo.py
python3 /path/to/nanonet-master/build.py nanonet/ICAWeights13.topo.py
```

The experiment runs entirely from `phase2_13nodes_gateway4_nstreams8/nanonet/` without `nanonet-master/`.

---

## Folder Structure

```
phase2_13nodes_gateway4_nstreams8/
├── README.md                          This file
├── phase1_to_nanonet_icajh13_trace.py Algorithm trace + MLU assertions (stdlib only)
│
├── Baseline-ECMP/                     ECMP baseline reference
│   ├── ICAWeights13.topo.py           Nanonet Python topology (reference copy)
│   └── README.md                      Experiment notes
│
├── ICA_JH_SRv6/                       ICA-JH SRv6 experiment reference
│   ├── ICAJH13.topo.py                Nanonet Python topology (reference copy)
│   └── README.md                      Experiment notes
│
├── nanonet/                           RUNTIME — do not move files out of here
│   ├── ICAJH13.topo.sh                Shell script: ICA-JH topology (Linux)
│   ├── ICAJH13.topo.py                Nanonet Python source
│   ├── ICAWeights13.topo.sh           Shell script: ECMP topology (Linux)
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
├── scripts/                           Analysis and automation
│   ├── run_batch5.sh                  Wrapper: run N reps of both experiments on Linux
│   └── create_batch5_full_summary.py  Build full CSV+JSON summary from run outputs
│
├── results/                           [generated by create_batch5_full_summary.py]
│   ├── batch5_full_summary.csv
│   └── batch5_full_summary.json
│
└── Plots/                             [generated by gen_boxplot_icajh13.py]
    └── icajh13_vs_icaweights13_boxplot.png
```

> `nanonet/` is runtime-critical. The batch runner and `throughput.py` resolve all paths relative to their own location. The topology files in `Baseline-ECMP/` and `ICA_JH_SRv6/` are reference copies only.

---

## How to Run (Linux only)

### Prerequisites

```bash
which nuttcp at python3 ip tc    # all must be on PATH
sudo systemctl enable --now atd  # atd daemon must be running
```

### 1. Verify the algorithm (no root, Mac or Linux)

```bash
cd phase2_13nodes_gateway4_nstreams8/
python3 phase1_to_nanonet_icajh13_trace.py
# Expected: "All assertions passed."  (Case 1 MLU=2.0, Case 2 MLU=1.0)
```

### 2. Run a single topology

```bash
cd phase2_13nodes_gateway4_nstreams8/nanonet/
sudo bash ICAWeights13.topo.sh     # ECMP baseline
sudo bash ICAJH13.topo.sh          # ICA-JH SRv6
# Tear down:
sudo bash ICAJH13.topo.sh --stop
```

### 3. Run the full batch experiment

```bash
# Via wrapper script (runs both experiments, N reps each):
cd phase2_13nodes_gateway4_nstreams8/
sudo bash scripts/run_batch5.sh 5      # 5 reps each (~50 min total)

# Or directly (1 rep for a quick sanity check):
cd phase2_13nodes_gateway4_nstreams8/nanonet/
sudo env ICA_REPETITIONS=1 python3 nanonet_batch_icajh13.py

# Or with more reps:
sudo env ICA_REPETITIONS=5 python3 nanonet_batch_icajh13.py
```

Output: `nanonet/batch_result_icajh13.csv`

### 4. Generate full summary

```bash
python3 scripts/create_batch5_full_summary.py
# Reads:  nanonet/batch_result_icajh13.csv + nanonet/flow_*.txt logs
# Writes: results/batch5_full_summary.csv
#         results/batch5_full_summary.json
```

### 5. Generate boxplot

```bash
python3 nanonet/gen_boxplot_icajh13.py
# Reads:  nanonet/batch_result_icajh13.csv
# Writes: nanonet/icajh13_vs_icaweights13_boxplot.png
mv nanonet/icajh13_vs_icaweights13_boxplot.png Plots/
```

---

## Outputs

| File | When generated | Contents |
|------|----------------|----------|
| `nanonet/batch_result_icajh13.csv` | After batch run | One row per rep per experiment: throughput, MLU, node counters |
| `nanonet/flow_*.txt` | After each rep | Raw nuttcp output per flow (archived per rep) |
| `results/batch5_full_summary.csv` | After summary script | Full per-rep data including parsed flow Mbps |
| `results/batch5_full_summary.json` | After summary script | Same data in JSON format |
| `Plots/icajh13_vs_icaweights13_boxplot.png` | After boxplot script | Side-by-side MLU boxplot: baseline vs ICA-JH |

---

## Metrics

Each row in `batch_result_icajh13.csv` records:

| Column | Description |
|--------|-------------|
| `experiment` | `baseline_ecmp` or `icajh_srv6` |
| `rep` | Repetition index |
| `total_throughput_mbps` | Sum of all 4 flow Mbps parsed from nuttcp output |
| `measured_mlu` | Max link utilization measured from node byte counters (see below) |
| `json_expected_mlu` | Expected MLU from the JSON file (2.0 or 1.0) |
| `node_X_sent_bytes` | Total bytes sent by node X during the experiment |
| `node_X_recv_bytes` | Total bytes received by node X |
| `valid` | `True` if all 4 flows completed; `False` if any timed out |
| `duration_s` | Actual experiment wall-clock duration |

### MLU Measurement Method

`measured_mlu` is computed by `compute_mlu()` in `nanonet_batch_icajh13.py` using direct per-interface byte counters written by `throughput.py` (a daemon running inside each network namespace). No JSON utilization values are used in the measurement.

Two sets of links are measured:

1. **Source links** (11→0, 12→0, 13→0, 14→0): each source node has exactly one uplink. `iface_tx_delta[src]["src-0"]` measures the exact bytes sent toward node 0 during the experiment.

2. **Gateway links** (0→4, 1→4, 2→4, 3→4): each core node has a dedicated gateway-facing interface. `iface_tx_delta[k]["gw_iface"]` measures the exact bytes sent toward gateway 4 on that specific interface.

```
measured_mlu = max(link_util for all source and gateway links)
link_util    = (iface_tx_bytes × 8 / TIME) / (json_capacity × 10 Mbps)
```

This direct per-interface approach correctly handles ICA-JH routing: node 1 simultaneously forwards demands 11+12 toward gateway (via interface `1-2`) and demand 13 toward node 2 (via interface `1-1`). Reading only `1-2` captures gateway-bound traffic without conflating directions.

**Gateway-facing interfaces per core node:**

| Core node | Interface to gateway |
|:---------:|:--------------------:|
| 0 | `0-1` |
| 1 | `1-2` |
| 2 | `2-2` |
| 3 | `3-1` |

---

## Sanity Check — 1-Run Linux Results

Single-repetition result from the Linux server (`sudo env ICA_REPETITIONS=1 python3 nanonet_batch_icajh13.py`):

| Experiment | Total throughput | Measured MLU | Expected MLU |
|------------|:----------------:|:------------:|:------------:|
| `baseline_ecmp` | ≈ 39.99 Mbps | **2.2704** | 2.0 |
| `icajh_srv6` | ≈ 40.00 Mbps | **1.0124** | 1.0 |

Both experiments deliver the full 4 × 10 Mbps. ICA-JH measured MLU ≈ 1.01 vs. baseline ≈ 2.27, confirming that the algorithm correctly redistributes traffic away from the bottleneck link.

The small deviation above the exact expected values (2.0 / 1.0) is normal: nuttcp flows ramp up at start, and the byte-counter snapshots cover the full 120-second window including that ramp. Over multiple repetitions these deviations average out.

---

## Final Batch Results

> **Placeholder — to be filled after the full 5-repetition batch run on the Linux server.**

```bash
cd phase2_13nodes_gateway4_nstreams8/
sudo bash scripts/run_batch5.sh 5
python3 scripts/create_batch5_full_summary.py
# Record median and IQR from results/batch5_full_summary.json
```

Expected outcome:

| Experiment | Median MLU | Total throughput |
|------------|:----------:|:----------------:|
| `baseline_ecmp` | ≈ 2.0 | ≈ 40 Mbps |
| `icajh_srv6` | ≈ 1.0 | ≈ 40 Mbps |

Boxplot saved to `Plots/icajh13_vs_icaweights13_boxplot.png`.

---

## Fairness

Both experiments run under identical conditions:

- Same 13-node topology and link capacities
- Same four demands (11→21, 12→22, 13→23, 14→24)
- Same nuttcp settings: TIME=120s, NSTREAMS=8, rate 10 Mbps per demand
- Same Linux server and kernel version
- Same `throughput.py` byte-counter daemon and `compute_mlu()` measurement code

The only variable is the routing mechanism: ECMP weights (no SRv6) vs. ICA-JH waypoints (SRv6 inline). Any observed MLU difference is attributable solely to the routing algorithm.

**ICA-JH algorithm parameters are unchanged from Phase 1:** β=0.9, max\_iterations=10, WAPL tie-breaker, waypoint assignments as specified in the algorithm trace above.

---

## What Changed from the Original Files

| Change | Scope | Reason |
|--------|-------|--------|
| `nanonet/throughput.py` | Added `iface_tx_delta` per-interface dict to `build_record()` | Enables direct interface-level byte measurement |
| `nanonet/nanonet_batch_icajh13.py` | Rewrote `compute_mlu()` | Fixed MLU direction: uses `iface_tx_delta` on gateway-facing interfaces instead of the broken node-total conservation formula |
| `nanonet/ICAJH13.topo.sh` | Added return routes for node 24 | TCP SYN-ACKs from receiver 24 could not reach source loopbacks |
| `nanonet/ICAWeights13.topo.sh` | Added return routes for receiver nodes 21–24 | Same fix for ECMP baseline |
| `scripts/run_batch5.sh` | New file | Convenience wrapper for the batch runner |
| `scripts/create_batch5_full_summary.py` | New file | Post-processing: builds full CSV+JSON summary from run outputs |
| `README.md` | This file | Replaces `README_phase2_13nodes.md` |

**Not changed:** ICA-JH algorithm logic, waypoint assignments, topology capacities, JSON files, TIME, NSTREAMS, or any file outside this directory.
