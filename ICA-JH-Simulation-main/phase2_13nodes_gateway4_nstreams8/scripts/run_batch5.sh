#!/usr/bin/env bash
# run_batch5.sh — Run N baseline + N ICA-JH experiments on Linux/Nanonet.
#
# Usage:
#   sudo bash scripts/run_batch5.sh [N]
#   sudo REPS=3 bash scripts/run_batch5.sh
#
# N / REPS = number of repetitions per experiment (default 5).
# Run from the phase2_13nodes_gateway4_nstreams8/ directory.
#
# What it does:
#   1. Calls nanonet/nanonet_batch_icajh13.py with ICA_REPETITIONS=N
#   2. That runner handles both experiments in sequence:
#        - ICAWeights13.topo.sh  (ECMP baseline, N repetitions)
#        - ICAJH13.topo.sh       (ICA-JH SRv6, N repetitions)
#   3. Writes nanonet/batch_result_icajh13.csv
#   4. Call scripts/create_batch5_full_summary.py afterwards to build summary.
#
# Requirements (Linux only):
#   - Nanonet installed and nanonet/ path accessible
#   - nuttcp, at, atd, ip, tc on PATH
#   - Must run as root (sudo)

set -euo pipefail

# Number of repetitions: env var REPS > positional arg > default 5
REPS="${REPS:-${1:-5}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NANONET_DIR="$PROJECT_DIR/nanonet"
BATCH_RUNNER="$NANONET_DIR/nanonet_batch_icajh13.py"

# Sanity checks
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo bash scripts/run_batch5.sh)" >&2
    exit 1
fi

if [[ ! -f "$BATCH_RUNNER" ]]; then
    echo "ERROR: batch runner not found: $BATCH_RUNNER" >&2
    exit 1
fi

echo "=============================================="
echo " Phase 2 batch experiment"
echo " Repetitions per experiment : $REPS"
echo " Experiments                : ICAWeights13 (ECMP) + ICAJH13 (SRv6)"
echo " Expected duration          : ~$((REPS * 10)) minutes  (2 experiments × 5 min/run × N reps)"
echo "=============================================="
echo ""

# Run from nanonet/ so relative paths in topo.sh resolve correctly
cd "$NANONET_DIR"

sudo env ICA_REPETITIONS="$REPS" python3 nanonet_batch_icajh13.py

echo ""
echo "Batch complete. CSV written to:"
echo "  $NANONET_DIR/batch_result_icajh13.csv"
echo ""
echo "Generate full summary:"
echo "  python3 $SCRIPT_DIR/create_batch5_full_summary.py"
echo ""
echo "Generate boxplot:"
echo "  python3 $NANONET_DIR/gen_boxplot_icajh13.py"
