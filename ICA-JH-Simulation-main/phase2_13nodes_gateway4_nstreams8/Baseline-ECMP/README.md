# Baseline-ECMP — ECMP Weights-Only Routing (No SRv6)

## What this is

This folder contains the **ECMP baseline** experiment for the Phase 2 comparison.

- **No SRv6**, no segment routing, no waypoints.
- Routing is determined purely by OSPF link weights (ICAWeights13 weight scheme).
- Traffic is split by ECMP at node 0 between the two equal-cost paths to gateway node 4.

## Expected Result

**MLU = 2.0**

With OSPF weights w(0→4)=2 (cost 2000) and w(1→4)=1 (cost 1000):
- Path 0→4 direct has OSPF cost 2000.
- Path 0→1→4 has OSPF cost 1000+1000 = 2000.
- Both paths have equal cost → ECMP splits traffic 2/2 across both paths.
- Link (0→4) carries 2 demands × 10 Mbps = 20 Mbps on a 10 Mbps link → **utilization = 2.0**.

This is the congestion point that ICA-JH with SRv6 waypoints resolves.

## Files in this folder

| File | Description |
|------|-------------|
| `ICAWeights13.topo.py` | Nanonet Python topology definition (reference copy) |
| `README.md` | This file |

## Runtime files (in `../nanonet/`)

The files that are actually executed on Linux live in `nanonet/`:

| File | Description |
|------|-------------|
| `nanonet/ICAWeights13.topo.sh` | Shell script — sets up 13 network namespaces, OSPF weights, ECMP routing, nuttcp clients/servers |
| `nanonet/ICAWeights13.topo.py` | Nanonet Python source for the shell script above |

The `.topo.sh` files are kept in `nanonet/` because the batch runner
(`nanonet_batch_icajh13.py`) locates them relative to its own directory.
Moving them would break the runner.

## Topology design

Same topology as ICA-JH: 13 nodes, gateway node 4, four demands (11→21, 12→22, 13→23, 14→24).
Only the routing differs:

| Link(s) | tc rate | JSON cap | Note |
|---------|---------|----------|------|
| Core 0-1, 1-2, 2-3 | 800 Mbps | 8 units | non-bottleneck |
| Gateway 0→4 | 100 Mbps | 1 unit | bottleneck (ECMP sends 2 flows here) |
| Gateway 1→4 | 200 Mbps | 2 units | wide link |
| Gateway 2→4, 3→4 | 100 Mbps | 1 unit | unused in this experiment |
| Source 1x→0 | 100 Mbps | 1 unit | one demand each |
| Receiver 4→2x | 10 Gbps | — | non-bottleneck |

tc rates are 10× maximum demand so they never cap nuttcp traffic.
1 unit = 10 Mbps = one nuttcp flow (`-R10000` kbit/s).

## How to run

```bash
# From the Linux host, nanonet/ directory:
cd path/to/phase2_13nodes_gateway4_nstreams8/nanonet

# Single run:
sudo bash ICAWeights13.topo.sh

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
