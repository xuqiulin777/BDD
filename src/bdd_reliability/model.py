from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Node:
    id: str
    reliability: float = 1.0


@dataclass
class Edge:
    id: str
    source: str
    target: str
    reliability: float = 1.0


@dataclass
class Constraints:
    subset_nodes: List[str] = field(default_factory=list)
    subset_max_fail: Optional[int] = None
    max_fail_nodes: Optional[int] = None
    nodes_max_hops: Optional[int] = None


@dataclass
class Topology:
    nodes: List[Node]
    edges: List[Edge]
    constraints: Constraints = field(default_factory=Constraints)
