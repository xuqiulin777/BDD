from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple


@dataclass(frozen=True)
class BDDNode:
    var: int
    low: int
    high: int


class ROBDD:
    """Small reduced ordered BDD implementation with unique-table + apply."""

    FALSE = 0
    TRUE = 1

    def __init__(self, var_count: int):
        self.var_count = var_count
        self.nodes: Dict[int, BDDNode] = {}
        self.unique: Dict[Tuple[int, int, int], int] = {}
        self._next_id = 2

    def mk(self, var: int, low: int, high: int) -> int:
        if low == high:
            return low
        key = (var, low, high)
        existing = self.unique.get(key)
        if existing is not None:
            return existing
        nid = self._next_id
        self._next_id += 1
        self.nodes[nid] = BDDNode(var=var, low=low, high=high)
        self.unique[key] = nid
        return nid

    def var(self, idx: int) -> int:
        return self.mk(idx, self.FALSE, self.TRUE)

    def _top_var(self, u: int) -> int:
        if u in (self.FALSE, self.TRUE):
            return self.var_count + 1
        return self.nodes[u].var

    def _cofactor(self, u: int, top: int) -> Tuple[int, int]:
        if u in (self.FALSE, self.TRUE):
            return u, u
        n = self.nodes[u]
        if n.var == top:
            return n.low, n.high
        return u, u

    def apply(self, op: Callable[[bool, bool], bool], u1: int, u2: int) -> int:
        memo: Dict[Tuple[int, int], int] = {}

        def rec(a: int, b: int) -> int:
            key = (a, b)
            if key in memo:
                return memo[key]
            if a in (self.FALSE, self.TRUE) and b in (self.FALSE, self.TRUE):
                val = op(a == self.TRUE, b == self.TRUE)
                r = self.TRUE if val else self.FALSE
                memo[key] = r
                return r
            t = min(self._top_var(a), self._top_var(b))
            al, ah = self._cofactor(a, t)
            bl, bh = self._cofactor(b, t)
            low = rec(al, bl)
            high = rec(ah, bh)
            r = self.mk(t, low, high)
            memo[key] = r
            return r

        return rec(u1, u2)

    def bdd_not(self, u: int) -> int:
        memo: Dict[int, int] = {}

        def rec(x: int) -> int:
            if x == self.FALSE:
                return self.TRUE
            if x == self.TRUE:
                return self.FALSE
            if x in memo:
                return memo[x]
            n = self.nodes[x]
            low = rec(n.low)
            high = rec(n.high)
            r = self.mk(n.var, low, high)
            memo[x] = r
            return r

        return rec(u)

    def bdd_and(self, u1: int, u2: int) -> int:
        return self.apply(lambda a, b: a and b, u1, u2)

    def bdd_or(self, u1: int, u2: int) -> int:
        return self.apply(lambda a, b: a or b, u1, u2)

    def evaluate_probability(self, root: int, p_up: Dict[int, float]) -> float:
        memo: Dict[int, float] = {}

        def rec(u: int) -> float:
            if u == self.FALSE:
                return 0.0
            if u == self.TRUE:
                return 1.0
            if u in memo:
                return memo[u]
            node = self.nodes[u]
            p = p_up[node.var]
            ans = p * rec(node.high) + (1 - p) * rec(node.low)
            memo[u] = ans
            return ans

        return rec(root)
