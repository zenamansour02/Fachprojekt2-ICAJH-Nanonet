# ICA-JH SRv6 — ICA-JH Algorithm with SRv6 Waypoints

## What this is

This folder contains the **ICA-JH SRv6** experiment for the Phase 2 comparison.

- Uses **SRv6 (Segment Routing IPv6)** with `encap seg6 mode inline` to steer traffic through waypoint nodes.
- Waypoints are computed by the ICA-JH algorithm (β=0.9, max_iterations=10, WAPL tie-breaker).
- Baseline OSPF weights: all gateway links w=4 (HeurOSPF starting point → initial MLU=4.0).
- After ICA-JH: MLU reduced to **1.0** (50% improvement over ECMP baseline).

## Expected Result

**MLU = 1.0**

ICA-JH assigns waypoints:
- Demand 11→4 via **waypoint node 1** (SRv6: 11→0→1→4→21)
- Demand 12→4 via **waypoint node 1** (SRv6: 12→0→1→4→22)
- Demand 13→4 via **waypoint node 2** (SRv6: 13→0→1→2→4→23)
- Demand 14→4 **direct** (no SRv6: 14→0→4→24)

Load distribution (1 unit = 1 nuttcp demand = 10 Mbps):
- Link (1→4): 2 demands × 10 Mbps on 2-unit (20 Mbps JSON) capacity → util = 1.0
- Link (0→4): 1 demand × 10 Mbps on 1-unit (10 Mbps JSON) capacity → util = 1.0
- Link (2→4): 1 demand × 10 Mbps on 1-unit (10 Mbps JSON) capacity → util = 1.0
- All links ≤ 1.0 → **MLU = 1.0**

tc rates are 10× JSON capacity (200 Mbps on (1→4), 100 Mbps elsewhere) so tc never
caps nuttcp traffic — the MLU model is enforced by traffic steering, not bandwidth policing.

## Files in this folder

| File | Description |
|------|-------------|
| `ICAJH13.topo.py` | Nanonet Python topology definition (reference copy) |
| `README.md` | This file |

## Runtime files (in `../nanonet/`)

| File | Description |
|------|-------------|
| `nanonet/ICAJH13.topo.sh` | Shell script — sets up 13 namespaces, SRv6 routes, nuttcp clients/servers |
| `nanonet/ICAJH13.topo.py` | Nanonet Python source for the shell script above |

The `.topo.sh` files are kept in `nanonet/` because the batch runner
(`nanonet_batch_icajh13.py`) locates them relative to its own directory.
Moving them would break the runner.

## SRv6 inline routing detail

SRv6 `encap seg6 mode inline` inserts a Segment Routing Header (SRH) directly into
the existing IPv6 packet (no outer encapsulation). The waypoint node processes the
SRH and pops the outer segment, after which the inner destination takes over routing.

Example for demand 11→21 (waypoint=1):

```bash
# In namespace 11:
ip -6 route add fc00:2:0:a::1  \   # → receiver 21 loopback
    encap seg6 mode inline segs fc00:2:0:2::1 \  # waypoint = node 1 loopback
    nexthop via fc00:42:0:1::2 \   # next hop toward node 0
    table 1

ip -6 rule add to fc00:2:0:a::/64 iif lo table 1
```

Packet path: 11 → 0 → (SRH dst=node1) → 1 → (SRH stripped, dst=node21) → 4 → 21

## ICA-JH algorithm parameters

| Parameter | Value |
|-----------|-------|
| β (congestion threshold) | 0.9 |
| max_iterations | 10 |
| Tie-breaker | WAPL (Weighted Average Path Length) |
| Starting weights | HeurOSPF (all gateway links w=4) |
| Candidate waypoints | nodes 0, 1, 2, 3 |

The algorithm is verified by `phase1_to_nanonet_icajh13_trace.py` at the project root.

## How to run

```bash
# From the Linux host, nanonet/ directory:
cd path/to/phase2_13nodes_gateway4_nstreams8/nanonet

# Single run:
sudo bash ICAJH13.topo.sh

# Full batch (5 repetitions each experiment):
cd ..
sudo bash scripts/run_batch5.sh 5
```

See the top-level `README.md` for complete instructions.

## Comparison

| Metric | Baseline ECMP | ICA-JH SRv6 |
|--------|---------------|-------------|
| Routing | ECMP weights | SRv6 waypoints |
| MLU (expected) | 2.0 | 1.0 |
| SRv6 used | No | Yes |
| Congested link | (0→4) at 2× capacity | none |
