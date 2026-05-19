from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Optional, Tuple

from .model import Constraints, Topology
from .robdd import ROBDD
from .utils import StageProfile


class ReliabilityService:
    def __init__(self, max_bdd_nodes: int = 200000, max_paths_per_pair: int = 400):
        self.max_bdd_nodes = max_bdd_nodes
        self.max_paths_per_pair = max_paths_per_pair

    def calculate(self, topo: Topology) -> float:
        result, _ = self.calculate_with_profile(topo)
        return result

    def calculate_with_profile(self, topo: Topology) -> Tuple[float, StageProfile]:
        total_start = time.perf_counter()
        if topo.constraints.max_fail_nodes is None:
            raise ValueError("constraints.max_fail_nodes is required")
        if not topo.nodes or not topo.edges:
            profile = StageProfile(0.0, 0.0, 0.0, 0.0, 0)
            return 0.0, profile

        t0 = time.perf_counter()
        node_vars = {n.id: i for i, n in enumerate(topo.nodes)}
        edge_base = len(topo.nodes)
        edge_vars = {e.id: edge_base + i for i, e in enumerate(topo.edges)}
        bdd = ROBDD(var_count=len(topo.nodes) + len(topo.edges))
        p_up = {}
        for n in topo.nodes:
            p_up[node_vars[n.id]] = self._prob(n.reliability)
        for e in topo.edges:
            p_up[edge_vars[e.id]] = self._prob(e.reliability)
        t1 = time.perf_counter()

        c_subset = self._subset_constraint(bdd, node_vars, topo.constraints, topo)
        self._guard_bdd_size(bdd)
        c_global = self._global_constraint(bdd, node_vars, topo.constraints, len(topo.nodes))
        self._guard_bdd_size(bdd)
        c_conn = self._connectivity_constraint(bdd, topo, node_vars, edge_vars)
        self._guard_bdd_size(bdd)
        root = bdd.bdd_and(bdd.bdd_and(c_subset, c_global), c_conn)
        self._guard_bdd_size(bdd)
        t2 = time.perf_counter()

        result = bdd.evaluate_probability(root, p_up)
        t3 = time.perf_counter()
        profile = StageProfile(
            build_vars_ms=(t1 - t0) * 1000,
            build_constraints_ms=(t2 - t1) * 1000,
            probability_ms=(t3 - t2) * 1000,
            total_ms=(t3 - total_start) * 1000,
            bdd_nodes=len(bdd.nodes) + 2,
        )
        return result, profile

    def _guard_bdd_size(self, bdd: ROBDD) -> None:
        if len(bdd.nodes) > self.max_bdd_nodes:
            raise RuntimeError(f"BDD size exceeds limit: {len(bdd.nodes)} > {self.max_bdd_nodes}")

    def _prob(self, x: float) -> float:
        if x > 1.0:
            x = x / 100.0
        return max(0.0, min(1.0, x))

    def _at_most_k_fail(self, bdd: ROBDD, vars_: List[int], k: Optional[int]) -> int:
        if k is None or k >= len(vars_):
            return ROBDD.TRUE
        if k < 0:
            return ROBDD.FALSE
        eq = [ROBDD.FALSE for _ in range(k + 1)]
        eq[0] = ROBDD.TRUE
        for var in vars_:
            x = bdd.var(var)
            notx = bdd.bdd_not(x)
            nxt = [ROBDD.FALSE for _ in range(k + 1)]
            nxt[0] = bdd.bdd_and(eq[0], x)
            for j in range(1, k + 1):
                t1 = bdd.bdd_and(eq[j], x)
                t2 = bdd.bdd_and(eq[j - 1], notx)
                nxt[j] = bdd.bdd_or(t1, t2)
            eq = nxt
        res = ROBDD.FALSE
        for e in eq:
            res = bdd.bdd_or(res, e)
        return res

    def _subset_constraint(self, bdd: ROBDD, node_vars: Dict[str, int], c: Constraints, topo: Topology) -> int:
        subset_ids = list(c.subset_nodes) if c.subset_nodes else [n.id for n in topo.nodes if getattr(n, "node_type", "normal") == "key"]
        if c.subset_max_fail is None or not subset_ids:
            return ROBDD.TRUE
        vars_ = [node_vars[nid] for nid in subset_ids if nid in node_vars]
        return self._at_most_k_fail(bdd, vars_, c.subset_max_fail)

    def _global_constraint(self, bdd: ROBDD, node_vars: Dict[str, int], c: Constraints, n: int) -> int:
        if c.max_fail_nodes is None:
            raise ValueError("constraints.max_fail_nodes is required")
        return self._at_most_k_fail(bdd, list(node_vars.values()), c.max_fail_nodes)

    def _connectivity_constraint(self, bdd: ROBDD, topo: Topology,
                                 node_vars: Dict[str, int], edge_vars: Dict[str, int]) -> int:
        c = topo.constraints
        hop = c.nodes_max_hops if c.nodes_max_hops is not None else len(topo.nodes)
        hop = max(1, min(hop, len(topo.nodes)))

        neighbors: Dict[str, List[str]] = {n.id: [] for n in topo.nodes}
        edge_map: Dict[frozenset, List[int]] = {}
        for e in topo.edges:
            neighbors[e.source].append(e.target)
            neighbors[e.target].append(e.source)
            edge_map.setdefault(frozenset((e.source, e.target)), []).append(edge_vars[e.id])

        root = ROBDD.TRUE
        ids = [n.id for n in topo.nodes]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                u, v = ids[i], ids[j]
                x_u = bdd.var(node_vars[u])
                x_v = bdd.var(node_vars[v])
                r_uv = self._reachable_bdd(bdd, u, v, hop, neighbors, edge_map, node_vars)
                imp = bdd.bdd_or(bdd.bdd_or(bdd.bdd_not(x_u), bdd.bdd_not(x_v)), r_uv)
                root = bdd.bdd_and(root, imp)
                self._guard_bdd_size(bdd)
        return root

    def _reachable_bdd(self, bdd: ROBDD, src: str, dst: str, hop: int,
                       neighbors: Dict[str, List[str]], edge_map: Dict[frozenset, List[int]],
                       node_vars: Dict[str, int]) -> int:
        paths = self._enumerate_paths(src, dst, hop, neighbors, self.max_paths_per_pair)
        if not paths:
            return ROBDD.FALSE
        acc = ROBDD.FALSE
        for path in paths:
            p = ROBDD.TRUE
            for nid in path:
                p = bdd.bdd_and(p, bdd.var(node_vars[nid]))
            for a, b in zip(path[:-1], path[1:]):
                choices = edge_map.get(frozenset((a, b)), [])
                e_bdd = ROBDD.FALSE
                for ev in choices:
                    e_bdd = bdd.bdd_or(e_bdd, bdd.var(ev))
                p = bdd.bdd_and(p, e_bdd)
            acc = bdd.bdd_or(acc, p)
            self._guard_bdd_size(bdd)
        return acc

    def _enumerate_paths(self, src: str, dst: str, hop: int, neighbors: Dict[str, List[str]],
                         limit: int) -> List[List[str]]:
        out: List[List[str]] = []
        q = deque([(src, [src])])
        while q:
            cur, path = q.popleft()
            if len(path) - 1 > hop:
                continue
            if cur == dst and len(path) > 1:
                out.append(path)
                if len(out) >= limit:
                    break
                continue
            if len(path) - 1 == hop:
                continue
            for nxt in neighbors[cur]:
                if nxt in path:
                    continue
                q.append((nxt, path + [nxt]))
        return out


