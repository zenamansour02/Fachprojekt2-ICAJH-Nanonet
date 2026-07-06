# Phase 2: ICA-JH 13-Node Gateway-4 Nanonet Experiment

## Overview

This directory contains a Nanonet emulation of the ICA-JH traffic-engineering
algorithm on a 13-node topology with gateway node 4 and 8 measurement streams.
The experiment compares ICA-JH (SRv6 waypoints) against ICAWeights13 (ECMP
baseline) and measures MLU (Maximum Link Utilization).

## Topology

```
Sources:   11, 12, 13, 14
Core:       0 --- 1 --- 2 --- 3
            |     |     |     |
            +--4--+--4--+--4--+   (gateway links, capacity 1 Tbit)
                  |
                  4  (gateway node)
                 /|\ \
               21 22 23 24  (receivers)
```

- Core links (0-1, 1-2, 2-3): **capacity 8 Tbit**, cost 1
- Gateway ingress links (x→4): **capacity 1 Tbit**, except **1→4 capacity 2 Tbit**
- Source links (11/12/13/14→0): **capacity 1 Tbit**, cost 1
- Receiver links (4→21/22/23/24): **capacity 1000 Tbit** (non-bottleneck)

**Active TE demands**:
- Demand 0: node 11 → gateway 4 (size 1)
- Demand 1: node 12 → gateway 4 (size 1)
- Demand 2: node 13 → gateway 4 (size 1)
- Demand 3: node 14 → gateway 4 (size 1)

**Measurement flows**:
- node 11 → receiver 21
- node 12 → receiver 22
- node 13 → receiver 23
- node 14 → receiver 24

## Algorithm Trace (verified by `phase1_to_nanonet_icajh13_trace.py`)

### Case 1: ICAWeights13 ECMP Baseline
- OSPF weights: w(0→4)=2, w(1→4)=1, core w=1
- Routing: 2-way ECMP at node 0 (splits traffic between 0→4 and 0→1→4)
- Result: **MLU = 2.0** (0→4 carries 2 demand units over capacity 1)

### Case 2: ICA-JH13 (SRv6 waypoints)
Starting from HeurOSPF weights (all gateway links w=4), MLU=4.0:

| Iteration | Event |
|-----------|-------|
| 1 | demand 0 (11→4) assigned wp=1: 11→0→1→4 → MLU=3.0 |
| 1 | demand 1 (12→4) assigned wp=1: 12→0→1→4 → MLU=2.0 |
| 1 | demand 2 (13→4) assigned wp=1: 13→0→1→4 → MLU=1.5 |
| 1 | demand 2 (13→4) reassigned wp=2: 13→0→1→2→4 → MLU=1.0 |
| 2 | no improvement → converged |

Final assignment: **demand 0 via wp=1 (SRv6)**, **demand 1 via wp=1 (SRv6)**,
**demand 2 via wp=2 (SRv6)**, demand 3 direct. **MLU = 1.0**
(50% improvement over ECMP baseline).

## Files

| File | Description |
|------|-------------|
| `json/icajh13_gateway4.json` | ICA-JH result: waypoints, utilizations, MLU=1.0 |
| `json/icaweights13_gateway4.json` | ECMP baseline: weights, utilizations, MLU=2.0 |
| `nanonet/ICAJH13.topo.py` | Nanonet Python topology (ICA-JH SRv6 routing) |
| `nanonet/ICAWeights13.topo.py` | Nanonet Python topology (ECMP routing) |
| `nanonet/ICAJH13.topo.sh` | Nanonet shell script (ICA-JH, all 13 namespaces) |
| `nanonet/ICAWeights13.topo.sh` | Nanonet shell script (ECMP, all 13 namespaces) |
| `nanonet/nanonet_batch_icajh13.py` | Batch runner (10 reps, writes CSV) |
| `nanonet/gen_boxplot_icajh13.py` | Boxplot generator (reads CSV, writes PNG) |
| `phase1_to_nanonet_icajh13_trace.py` | Trace script (stdlib-only, asserts MLU) |
| `README_phase2_13nodes.md` | This file |

## Parameters

| Parameter | Value |
|-----------|-------|
| TIME | 120 s |
| NSTREAMS | 8 |
| DEMAND_FACTOR | 10000 |
| ICA-JH β | 0.9 |
| ICA-JH max_iterations | 10 |
| Default repetitions | 10 (override: `ICAJH13_REPETITIONS=N`) |

## Loopback Addresses

| Node | Loopback |
|------|----------|
| 11 | fc00:2:0:1::1 |
| 1 | fc00:2:0:2::1 |
| 3 | fc00:2:0:3::1 |
| 13 | fc00:2:0:4::1 |
| 2 | fc00:2:0:5::1 |
| 0 | fc00:2:0:6::1 |
| 4 | fc00:2:0:7::1 |
| 12 | fc00:2:0:8::1 |
| 14 | fc00:2:0:9::1 |
| 21 | fc00:2:0:a::1 |
| 22 | fc00:2:0:b::1 |
| 23 | fc00:2:0:c::1 |
| 24 | fc00:2:0:d::1 |

## Build / Run

### Prerequisites (Linux only)

Nanonet requires Linux network namespaces, `iproute2`, `tc` (iproute2 traffic
control), `nuttcp`, and the `at` scheduler. All topo.sh scripts use only
standard Linux tools: `ip`, `ifconfig`, `tc`, `sysctl`, `nuttcp`, `at`.
No macOS tools are used.

```bash
# Confirm Nanonet is installed and nuttcp is on PATH:
which nuttcp
which at
# Enable atd if needed:
sudo systemctl enable --now atd
```

### Verify algorithm (stdlib only, runs on any Python 3.6+)

Run from the `phase2_13nodes_gateway4_nstreams8/` directory:

```bash
python3 phase1_to_nanonet_icajh13_trace.py
# Expected: "All assertions passed." (Case 1 MLU=2.0, Case 2 MLU=1.0)
```

### Run single topology

Run from the `nanonet/` directory:

```bash
cd ICA-JH-Simulation-main/phase2_13nodes_gateway4_nstreams8/nanonet
sudo bash ICAJH13.topo.sh        # ICA-JH (SRv6 waypoints)
sudo bash ICAWeights13.topo.sh   # ECMP baseline
# To tear down: sudo bash ICAJH13.topo.sh --stop
```

### Run full batch experiment

Run from the `nanonet/` directory (the script uses `__file__` to locate all
paths, so the working directory does not matter, but running from nanonet/ is
conventional):

```bash
cd ICA-JH-Simulation-main/phase2_13nodes_gateway4_nstreams8/nanonet
sudo python3 nanonet_batch_icajh13.py
# Output: nanonet/batch_result_icajh13.csv
# Override repetition count (default 10):
sudo ICAJH13_REPETITIONS=3 python3 nanonet_batch_icajh13.py
```

### Generate boxplot

```bash
cd ICA-JH-Simulation-main/phase2_13nodes_gateway4_nstreams8/nanonet
python3 gen_boxplot_icajh13.py
# Reads: nanonet/batch_result_icajh13.csv
# Output: nanonet/icajh13_vs_icaweights13_boxplot.png
```

### Regenerate topo.sh files (on Linux with Nanonet build.py)

The `.topo.sh` files were hand-crafted from the deterministic address scheme
defined in this README. To regenerate from `.topo.py` using Nanonet's
`build.py` (must be on a Linux host with Nanonet installed):

```bash
cd ICA-JH-Simulation-main/phase2_13nodes_gateway4_nstreams8/nanonet
python3 /path/to/nanonet/build.py ICAJH13.topo.py
python3 /path/to/nanonet/build.py ICAWeights13.topo.py
```

## SRv6 Routing Detail

ICA-JH routes demand 11→receivers via waypoint node 1:

```
Node 11: ip -6 route add fc00:2:0:a::1 encap seg6 mode inline segs fc00:2:0:2::1
```

Packet path: 11 → 0 → 1 (seg6 stripped) → 4 → 21

Demand 12→receivers via waypoint node 2:

```
Node 12: ip -6 route add fc00:2:0:b::1 encap seg6 mode inline segs fc00:2:0:2::1
```

Packet path: 12 → 0 → 1 (seg6 stripped) → 4 → 22

Demand 13→receivers via waypoint node 2:

```
Node 13: ip -6 route add fc00:2:0:c::1 encap seg6 mode inline segs fc00:2:0:5::1
```

Packet path: 13 → 0 → 1 → 2 (seg6 stripped) → 4 → 23

Demand 14→receiver 24: direct (no SRv6).
