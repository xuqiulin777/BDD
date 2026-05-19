from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass
from typing import Dict, List

from .model import Constraints, Edge, Node, Topology


@dataclass
class StageProfile:
    build_vars_ms: float
    build_constraints_ms: float
    probability_ms: float
    total_ms: float
    bdd_nodes: int


def random_topology(node_count: int = 12, edge_count: int = 18, seed: int = 42) -> Dict:
    rnd = random.Random(seed)
    node_count = max(2, node_count)
    max_edges = node_count * (node_count - 1) // 2
    edge_count = min(max(node_count - 1, edge_count), max_edges)

    node_ids = [f"N{i+1}" for i in range(node_count)]
    nodes = [
        {
            "id": nid,
            "reliability": round(rnd.uniform(0.94, 0.999), 4),
        }
        for nid in node_ids
    ]

    chosen = set()
    edges: List[Dict] = []

    # ensure connected backbone
    for i in range(1, node_count):
        a = node_ids[i - 1]
        b = node_ids[i]
        key = tuple(sorted((a, b)))
        chosen.add(key)
        edges.append({
            "id": f"e{len(edges) + 1}",
            "source": a,
            "target": b,
            "reliability": round(rnd.uniform(0.95, 0.999), 4),
        })

    # add extra random edges
    all_pairs = [(node_ids[i], node_ids[j]) for i in range(node_count) for j in range(i + 1, node_count)]
    rnd.shuffle(all_pairs)
    for a, b in all_pairs:
        if len(edges) >= edge_count:
            break
        key = tuple(sorted((a, b)))
        if key in chosen:
            continue
        chosen.add(key)
        edges.append({
            "id": f"e{len(edges) + 1}",
            "source": a,
            "target": b,
            "reliability": round(rnd.uniform(0.95, 0.999), 4),
        })

    subset_size = max(2, min(6, node_count // 2))
    subset_nodes = rnd.sample(node_ids, subset_size)

    constraints = {
        "subset_nodes": subset_nodes,
        "subset_max_fail": max(0, subset_size // 3),
        "max_fail_nodes": max(0, node_count // 5),
        "nodes_max_hops": min(node_count, 4),
    }

    return {"nodes": nodes, "edges": edges, "constraints": constraints}
