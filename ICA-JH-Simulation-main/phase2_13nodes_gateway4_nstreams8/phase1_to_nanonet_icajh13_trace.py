#!/usr/bin/env python3
"""
Phase 1 → Phase 2 trace: ICA-JH algorithm for the 13-node gateway-4 topology.

Stdlib-only implementation (no networkit, no numpy).
Runs two cases and asserts expected MLU values:
  Case 1: ICAWeights13 ECMP weights  →  MLU = 2.0
  Case 2: ICA-JH13 SRv6 waypoints   →  MLU = 1.0

The ICA-JH algorithm implemented here keeps the Phase 1 logic, scaled to
13 nodes.
"""

import heapq
from collections import defaultdict

# ---------------------------------------------------------------------------
# Topology definition
# ---------------------------------------------------------------------------

# Directed links: (src, dst, capacity_units, heurospf_weight, ecmp_weight)
# capacity=8 for core links, capacity=1 for gateway/source, capacity=1000 for receivers
# heurospf_weight=4 for all gateway ingress (ICAJH13 OSPF starting point)
# ecmp_weight: w(0->4)=2, w(1->4)=1, core=1 (ICAWeights13 baseline)

NODES = [0, 1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24]

LINKS_RAW = [
    # (src, dst, capacity, heurospf_w, ecmp_w)
    (0,  1,  8, 1, 1),   (1,  0,  8, 1, 1),
    (1,  2,  8, 1, 1),   (2,  1,  8, 1, 1),
    (2,  3,  8, 1, 1),   (3,  2,  8, 1, 1),
    (0,  4,  1, 4, 2),   (4,  0,  1, 4, 4),
    (1,  4,  2, 4, 1),   (4,  1,  1, 4, 4),
    (2,  4,  1, 4, 4),   (4,  2,  1, 4, 4),
    (3,  4,  1, 4, 4),   (4,  3,  1, 4, 4),
    (11, 0,  1, 1, 1),   (0, 11,  1, 1, 1),
    (12, 0,  1, 1, 1),   (0, 12,  1, 1, 1),
    (13, 0,  1, 1, 1),   (0, 13,  1, 1, 1),
    (14, 0,  1, 1, 1),   (0, 14,  1, 1, 1),
    (4, 21, 1000, 1, 1), (21, 4, 1000, 1, 1),
    (4, 22, 1000, 1, 1), (22, 4, 1000, 1, 1),
    (4, 23, 1000, 1, 1), (23, 4, 1000, 1, 1),
    (4, 24, 1000, 1, 1), (24, 4, 1000, 1, 1),
]

# Active demands
DEMANDS = [
    {"src": 11, "dst": 4, "size": 1},
    {"src": 12, "dst": 4, "size": 1},
    {"src": 13, "dst": 4, "size": 1},
    {"src": 14, "dst": 4, "size": 1},
]

BETA            = 0.9    # ICA-JH congestion threshold (unchanged from Phase 1)
MAX_ITERATIONS  = 10     # ICA-JH max iterations (unchanged from Phase 1)


# ---------------------------------------------------------------------------
# Graph utilities
# ---------------------------------------------------------------------------

def build_graph(weights):
    """Return adjacency dict {src: [(dst, cost, capacity)]} for given weight dict."""
    g = defaultdict(list)
    for (s, d, cap, _, _) in LINKS_RAW:
        w = weights.get((s, d), 1)
        g[s].append((d, w, cap))
    return g


def dijkstra(graph, src):
    """Single-source shortest path. Returns dist dict and prev dict."""
    dist = {n: float("inf") for n in NODES}
    prev = {n: None for n in NODES}
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for (v, w, _cap) in graph[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def shortest_path(graph, src, dst):
    """Return list of nodes on the shortest path from src to dst."""
    dist, prev = dijkstra(graph, src)
    if dist[dst] == float("inf"):
        return []
    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def ecmp_flow(weights, src, dst, size):
    """
    Compute link loads for one demand using hop-by-hop ECMP.
    Each node splits traffic equally among all equal-cost-shortest-path next-hops.
    Returns {(u,v): load} dict.
    """
    INF = float("inf")

    # Build forward adjacency with weights
    fwd = defaultdict(list)
    for row in LINKS_RAW:
        s, d, cap, hw, ew = row
        w = weights.get((s, d), 1)
        fwd[s].append((d, w))

    # Dijkstra from src to get dist_from_src
    dist_s = {n: INF for n in NODES}
    dist_s[src] = 0
    pq = [(0, src)]
    while pq:
        dd, u = heapq.heappop(pq)
        if dd > dist_s[u]:
            continue
        for (v, w) in fwd[u]:
            nd = dd + w
            if nd < dist_s[v]:
                dist_s[v] = nd
                heapq.heappush(pq, (nd, v))

    # Build reverse adjacency with weights
    rev = defaultdict(list)
    for row in LINKS_RAW:
        s, d, cap, hw, ew = row
        w = weights.get((s, d), 1)
        rev[d].append((s, w))

    # Dijkstra from dst on reverse graph → dist_to_dst[n]
    dist_d = {n: INF for n in NODES}
    dist_d[dst] = 0
    pq = [(0, dst)]
    while pq:
        dd, u = heapq.heappop(pq)
        if dd > dist_d[u]:
            continue
        for (v, w) in rev[u]:
            nd = dd + w
            if nd < dist_d[v]:
                dist_d[v] = nd
                heapq.heappush(pq, (nd, v))

    sp_dist = dist_s[dst]
    if sp_dist == INF:
        return {}

    # Process nodes in topological order (increasing dist_from_src)
    # A node u is on a shortest path if dist_s[u] + dist_d[u] == sp_dist
    on_sp = [n for n in NODES if dist_s[n] + dist_d[n] == sp_dist]
    on_sp.sort(key=lambda n: dist_s[n])

    link_load = defaultdict(float)
    flow_at = {src: float(size)}

    for u in on_sp:
        if u == dst:
            continue
        f = flow_at.get(u, 0.0)
        if f == 0.0:
            continue
        # ECMP next-hops: neighbors v on shortest path where w(u,v) + dist_d[v] == dist_d[u]
        nhs = []
        for (v, w) in fwd[u]:
            if abs(w + dist_d[v] - dist_d[u]) < 1e-12 and dist_s[u] + dist_d[u] == sp_dist:
                if dist_s[v] + dist_d[v] == sp_dist:
                    nhs.append(v)
        if not nhs:
            continue
        split = f / len(nhs)
        for v in nhs:
            link_load[(u, v)] += split
            flow_at[v] = flow_at.get(v, 0.0) + split

    return link_load


def compute_mlu(weights, waypoints):
    """
    Compute MLU given OSPF weights and per-demand waypoints.
    waypoints: {demand_index: waypoint_node} or {} for direct routing.
    Uses hop-by-hop ECMP for each demand segment.
    """
    combined_load = defaultdict(float)

    for i, dem in enumerate(DEMANDS):
        src, dst, size = dem["src"], dem["dst"], dem["size"]
        wp = waypoints.get(i)
        if wp is not None and wp != dst:
            # Two-segment routing: src→wp then wp→dst
            load1 = ecmp_flow(weights, src, wp, size)
            load2 = ecmp_flow(weights, wp, dst, size)
            for k, v in load1.items():
                combined_load[k] += v
            for k, v in load2.items():
                combined_load[k] += v
        else:
            load = ecmp_flow(weights, src, dst, size)
            for k, v in load.items():
                combined_load[k] += v

    # Link capacity map
    cap = {(s, d): cap for (s, d, cap, _, _) in LINKS_RAW}

    mlu = 0.0
    for (s, d), load in combined_load.items():
        util = load / cap[(s, d)]
        if util > mlu:
            mlu = util
    return mlu, combined_load


# ---------------------------------------------------------------------------
# ICA-JH algorithm (exact Phase 1 logic)
# ---------------------------------------------------------------------------

def wapl(weights, waypoints):
    """Weighted average path length for the current routing."""
    graph = build_graph(weights)
    total = 0.0
    for i, dem in enumerate(DEMANDS):
        src, dst, size = dem["src"], dem["dst"], dem["size"]
        wp = waypoints.get(i)
        if wp is not None and wp != dst:
            p1 = shortest_path(graph, src, wp)
            p2 = shortest_path(graph, wp, dst)
            path = p1 + p2[1:]
        else:
            path = shortest_path(graph, src, dst)
        total += (len(path) - 1) * size
    return total


def icajh(weights_key):
    """
    Run ICA-JH starting from the given weight scheme.
    weights_key: "heurospf" or "ecmp"
    Returns (best_waypoints, best_mlu, iteration_log).
    """
    w_idx = 3 if weights_key == "heurospf" else 4
    weights = {(s, d): row[w_idx] for (s, d, cap, hw, ew) in [(r[0],r[1],r[2],r[3],r[4]) for r in LINKS_RAW]
               for row in [LINKS_RAW] if False}
    # build weights dict properly
    weights = {}
    for row in LINKS_RAW:
        s, d, cap, hw, ew = row
        weights[(s, d)] = hw if weights_key == "heurospf" else ew

    best_waypoints = {}
    best_mlu, _ = compute_mlu(weights, best_waypoints)
    log = [f"Iteration 0 (init, no waypoints): MLU={best_mlu:.4f}"]

    candidate_waypoints_list = [0, 1, 2, 3]  # core + gateway nodes

    for iteration in range(1, MAX_ITERATIONS + 1):
        improved = False
        for i, dem in enumerate(DEMANDS):
            for wp in candidate_waypoints_list:
                if wp == dem["dst"]:
                    continue
                test_wp = dict(best_waypoints)
                test_wp[i] = wp
                test_mlu, _ = compute_mlu(weights, test_wp)
                # Strict improvement guard (same as Phase 1: test_mlu < best_mlu - 1e-9)
                if test_mlu < best_mlu - 1e-9:
                    best_mlu = test_mlu
                    best_waypoints = test_wp
                    improved = True
                    log.append(f"  Iteration {iteration}: demand {i} ({dem['src']}->{dem['dst']}) "
                               f"via wp={wp} → MLU={best_mlu:.4f}")
                elif abs(test_mlu - best_mlu) < 1e-9:
                    # WAPL tie-breaker: accept if shorter average path
                    if wapl(weights, test_wp) < wapl(weights, best_waypoints) - 1e-9:
                        best_waypoints = test_wp
                        log.append(f"  Iteration {iteration}: demand {i} wp={wp} "
                                   f"WAPL tie-break accepted MLU={best_mlu:.4f}")
        if not improved:
            log.append(f"Iteration {iteration}: no strict improvement → converged")
            break
        # Check BETA threshold: if MLU < beta * 1.0 (capacity normalized to 1)
        if best_mlu < BETA:
            log.append(f"Iteration {iteration}: MLU={best_mlu:.4f} < beta={BETA} → early stop")
            break

    return best_waypoints, best_mlu, log


# ---------------------------------------------------------------------------
# Case 1: ICAWeights13 ECMP baseline
# ---------------------------------------------------------------------------

def case1_icaweights13():
    print("=" * 60)
    print("Case 1: ICAWeights13 ECMP baseline (no SRv6 waypoints)")
    print("  w(0->4)=2, w(1->4)=1, core w=1")
    print("  Four demands: 11->4, 12->4, 13->4, 14->4 (direct, no waypoints)")

    weights = {(s, d): ew for (s, d, cap, hw, ew) in LINKS_RAW}
    waypoints = {}  # no waypoints — pure ECMP routing
    mlu, link_load = compute_mlu(weights, waypoints)

    print(f"\n  Link loads (non-zero):")
    cap_map = {(s, d): cap for (s, d, cap, _, _) in LINKS_RAW}
    for (s, d), load in sorted(link_load.items()):
        util = load / cap_map[(s, d)]
        if load > 0:
            print(f"    ({s},{d}): load={load:.3f}  cap={cap_map[(s,d)]}  util={util:.4f}")

    print(f"\n  MLU = {mlu:.4f}")
    assert abs(mlu - 2.0) < 1e-9, f"Expected MLU=2.0 but got {mlu}"
    print("  ASSERT PASSED: MLU == 2.0")


# ---------------------------------------------------------------------------
# Case 2: ICA-JH13 (starting from ECMP weights)
# ---------------------------------------------------------------------------

def case2_icajh13():
    print()
    print("=" * 60)
    print("Case 2: ICA-JH13 (SRv6 waypoints, starting from HeurOSPF)")
    print("  ICA-JH parameters: beta=0.9, max_iterations=10")
    print("  Starting state: HeurOSPF (all gateway links w=4) → MLU=4.0")
    print("  ICA-JH assigns SRv6 waypoints to reduce MLU to 1.0")

    waypoints, mlu, log = icajh("heurospf")

    print(f"\n  ICA-JH iteration log:")
    for line in log:
        print(f"    {line}")

    cap_map = {(s, d): cap for (s, d, cap, _, _) in LINKS_RAW}
    weights_h = {(s, d): hw for (s, d, cap, hw, ew) in LINKS_RAW}
    _, link_load = compute_mlu(weights_h, waypoints)

    print(f"\n  Final waypoints: {waypoints}")
    print(f"    demand 0 (11->4): wp={waypoints.get(0, 'direct')}")
    print(f"    demand 1 (12->4): wp={waypoints.get(1, 'direct')}")
    print(f"    demand 2 (13->4): wp={waypoints.get(2, 'direct')}")
    print(f"    demand 3 (14->4): wp={waypoints.get(3, 'direct')}")

    print(f"\n  Link loads (non-zero, using HeurOSPF routing):")
    for (s, d), load in sorted(link_load.items()):
        util = load / cap_map[(s, d)]
        if load > 0:
            print(f"    ({s},{d}): load={load:.3f}  cap={cap_map[(s,d)]}  util={util:.4f}")

    print(f"\n  MLU = {mlu:.4f}")
    assert abs(mlu - 1.0) < 1e-9, f"Expected MLU=1.0 but got {mlu}"
    print("  ASSERT PASSED: MLU == 1.0")

    print(f"\n  Phase 1 -> Phase 2 connection:")
    print(f"  Same ICA-JH algorithm (beta=0.9, WAPL tie-break) achieves")
    print(f"  MLU reduction from 4.0 (HeurOSPF, no waypoints) → 1.0")
    print(f"  by assigning SRv6 waypoints:")
    print(f"    demand 0 (11->4) via waypoint {waypoints.get(0, 'direct')} (SRv6 encap seg6)")
    print(f"    demand 1 (12->4) via waypoint {waypoints.get(1, 'direct')} (SRv6 encap seg6)")
    print(f"    demand 2 (13->4): {'direct (no SRv6)' if waypoints.get(2) is None else 'via wp='+str(waypoints.get(2))}")
    print(f"    demand 3 (14->4): {'direct (no SRv6)' if waypoints.get(3) is None else 'via wp='+str(waypoints.get(3))}")
    print(f"  ICA-JH vs ECMP baseline: 1.0 vs 2.0 → 50% MLU reduction")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Phase 1 -> Phase 2 ICA-JH trace: 13-node gateway-4 topology")
    print("Four demands: 11->4, 12->4, 13->4, 14->4")
    print()
    case1_icaweights13()
    case2_icajh13()
    print()
    print("=" * 60)
    print("All assertions passed.")
