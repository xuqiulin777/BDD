import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bdd_reliability.model import Constraints, Edge, Node, Topology
from bdd_reliability.service import ReliabilityService
from bdd_reliability.utils import random_topology


def test_basic_range():
    topo = Topology(
        nodes=[Node("A", 1.0), Node("B", 1.0)],
        edges=[Edge("e1", "A", "B", 1.0)],
        constraints=Constraints(max_fail_nodes=0, nodes_max_hops=1),
    )
    r = ReliabilityService().calculate(topo)
    assert 0.0 <= r <= 1.0


def test_perfect_network_is_one():
    topo = Topology(
        nodes=[Node("A", 1.0), Node("B", 1.0), Node("C", 1.0)],
        edges=[Edge("e1", "A", "B", 1.0), Edge("e2", "B", "C", 1.0), Edge("e3", "A", "C", 1.0)],
        constraints=Constraints(max_fail_nodes=0, nodes_max_hops=2),
    )
    r = ReliabilityService().calculate(topo)
    assert abs(r - 1.0) < 1e-12


def test_profile_and_random_topology():
    payload = random_topology(node_count=8, edge_count=12, seed=1)
    topo = Topology(
        nodes=[Node(**n) for n in payload["nodes"]],
        edges=[Edge(**e) for e in payload["edges"]],
        constraints=Constraints(**payload["constraints"]),
    )
    r, prof = ReliabilityService().calculate_with_profile(topo)
    assert 0.0 <= r <= 1.0
    assert prof.total_ms >= 0
    assert prof.bdd_nodes >= 2
