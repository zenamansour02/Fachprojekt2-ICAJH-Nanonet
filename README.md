# ICA-JH / Nanonet SRv6 Traffic Engineering Experiment

## Overview

This repository contains a Nanonet test-bed experiment comparing two routing configurations on the same emulated network:

1. **ECMP/weights-only baseline** — shortest-path / ECMP-style routing without SRv6.
2. **ICA-JH/SRv6** — routing with SRv6 waypoints computed from the ICA-JH traffic-engineering solution.

ICA-JH is computed offline. Its output — link weights, per-demand SRv6 waypoints, and objective MLU — is stored in the included JSON solution file. Nanonet does not optimize; it builds Linux network namespaces and applies the pre-computed routing configuration. `nuttcp` measures per-flow TCP throughput. All optimization happens offline before measurement.

## External dependency: Nanonet

`nanonet-master` is included next to this experiment folder inside `Fachprojekt2/`. It is the Nanonet build toolchain and is **not required for runtime** — the `.topo.sh` scripts used by this experiment are already generated and included.

`nanonet-master` is only needed to regenerate `.topo.sh` files from `.topo.py` if the topology definition changes:

```bash
python3 ../nanonet-master/build.py nanonet/ICAWeights13.topo.py
python3 ../nanonet-master/build.py nanonet/ICAJH13.topo.py
```

## Run the test scripts directly

### System requirements

- Linux with SRv6-capable kernel (kernel > 4.17 recommended)
- `sudo` privileges (network namespaces are created and deleted)
- iproute2: `ip`, `ip netns`, `ss`, `tc`
- `bash`, `python3`
- `at` / `atd`
- `nuttcp` — used for TCP flow measurements; this experiment uses `TIME=120s` and `NSTREAMS=8`

Installation example for Debian/Ubuntu:

```bash
sudo apt install nuttcp at iproute2
```

## Files

| File / folder | Description |
|---|---|
| `Baseline-ECMP/` | Baseline topology source and reference files |
| `ICA_JH_SRv6/` | ICA-JH topology source and reference files |
| `json/icaweights13_gateway4.json` | Baseline JSON reference result |
| `json/icajh13_gateway4.json` | ICA-JH JSON solution / reference result |
| `nanonet/ICAWeights13.topo.sh` | Generated baseline topology shell script (runtime) |
| `nanonet/ICAJH13.topo.sh` | Generated ICA-JH/SRv6 topology shell script (runtime) |
| `nanonet/nanonet_batch_icajh13.py` | Batch experiment runner |
| `nanonet/throughput.py` | Custom per-interface byte-counter daemon |
| `nanonet/gen_boxplot_icajh13.py` | Boxplot generator |
| `scripts/run_batch5.sh` | Wrapper for repeated batch runs |
| `scripts/create_batch5_full_summary.py` | Summary CSV/JSON generator |
| `results/` | Generated CSV/JSON summaries and archived run directories |
| `Plots/` | Generated plots |
| `phase1_to_nanonet_icajh13_trace.py` | Waypoint logic and MLU verification helper |

## Included ICA-JH solution

The pre-computed ICA-JH solution is stored in `json/icajh13_gateway4.json`. The corresponding baseline is in `json/icaweights13_gateway4.json`.

- Sources: 11, 12, 13, 14
- Gateway: 4
- Receivers: 21, 22, 23, 24
- Measurement flows: 11→21, 12→22, 13→23, 14→24

Routing decision:

| Demand | Route |
|---|---|
| 11 → 21 | via waypoint 1 |
| 12 → 22 | via waypoint 1 |
| 13 → 23 | via waypoint 2 |
| 14 → 24 | direct |

- ICA-JH expected MLU: **1.0**
- ECMP baseline expected MLU: **2.0**

## Execution

```bash
cd ~/Fachprojekt2/phase2_13nodes_gateway4_nstreams8
```

Run N repetitions of each variant:

```bash
sudo bash scripts/run_batch5.sh N
```

Build full CSV/JSON summary:

```bash
python3 scripts/create_batch5_full_summary.py
```

Generate MLU boxplot:

```bash
python3 nanonet/gen_boxplot_icajh13.py
```

`N` controls the number of repetitions. Use `N=1` for a sanity check; use `N=10` for the final batch. The script name `run_batch5.sh` is historical — `N` determines the actual repetition count.

## Results

Output files:

- `nanonet/batch_result_icajh13.csv` — raw per-run results (one row per repetition per variant)
- `results/batch5_full_summary.csv` — full summary including parsed per-flow Mbps
- `results/batch5_full_summary.json` — same data in JSON format
- `results/run_1_test/` — archived sanity-check run
- `nanonet/flow_*.txt*` — archived per-flow nuttcp logs
- `Plots/` — generated boxplot PNG files

Sanity-check result (1 repetition, Linux server):

| Variant | Total throughput | Measured MLU | Expected MLU |
|---|:---:|:---:|:---:|
| `baseline_ecmp` | ≈ 39.99 Mbps | 2.2704 | 2.0000 |
| `icajh_srv6` | ≈ 40.00 Mbps | 1.0124 | 1.0000 |

Both variants deliver the offered load. The key improvement is MLU reduction: ICA-JH reduces bottleneck link utilization from approximately 2.27 to approximately 1.01. This demonstrates better load balancing, not a throughput gain.


## Evaluation and plotting

`scripts/create_batch5_full_summary.py` reads `nanonet/batch_result_icajh13.csv` and the archived `flow_*.txt` logs to produce `results/batch5_full_summary.csv` and `results/batch5_full_summary.json`. Repeated runs are archived under separate subdirectories inside `results/`.

`nanonet/gen_boxplot_icajh13.py` reads the batch CSV and writes a side-by-side MLU boxplot to `Plots/`. It operates on existing result files and does not re-run experiments.

## Compile and configure the experiments

### Prepared topology scripts

The prepared topology scripts are already included and require no compilation:

```
nanonet/ICAWeights13.topo.sh   (baseline)
nanonet/ICAJH13.topo.sh        (ICA-JH/SRv6)
```

### Regenerate topology scripts

To regenerate `.topo.sh` files after modifying the topology definition:

```bash
python3 ../nanonet-master/build.py nanonet/ICAWeights13.topo.py
python3 ../nanonet-master/build.py nanonet/ICAJH13.topo.py
```

This step is not required for normal execution.

## Notes

- Receivers 21–24 are measurement endpoints behind gateway node 4.
- Both variants use the same topology, link capacities, traffic demands, and nuttcp settings (`TIME=120s`, `NSTREAMS=8`).
- The baseline variant uses no SRv6. The ICA-JH variant uses SRv6 inline waypoints applied at source nodes only.
- Nanonet is a runtime emulation framework, not a routing optimizer.
- MLU is measured from direct per-interface byte counters via `throughput.py`. No hardcoded JSON values are used in the measurement.
- No routing or topology changes are made during measurement.
