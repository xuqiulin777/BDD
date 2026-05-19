import json
import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bdd_reliability.model import Constraints, Edge, Node, Topology
from bdd_reliability.service import ReliabilityService
from bdd_reliability.utils import random_topology


st.set_page_config(page_title="BDD 网络可靠度计算器", layout="wide")
st.title("BDD 网络拓扑可靠度计算器（Python 版）")

service = ReliabilityService()

sample = {
    "nodes": [
        {"id": "A", "reliability": 0.99},
        {"id": "B", "reliability": 0.98},
        {"id": "C", "reliability": 0.97},
        {"id": "D", "reliability": 0.96},
    ],
    "edges": [
        {"id": "e1", "source": "A", "target": "B", "reliability": 0.995},
        {"id": "e2", "source": "B", "target": "C", "reliability": 0.992},
        {"id": "e3", "source": "C", "target": "D", "reliability": 0.993},
        {"id": "e4", "source": "A", "target": "D", "reliability": 0.990},
    ],
    "constraints": {
        "subset_nodes": ["A", "B", "C"],
        "subset_max_fail": 1,
        "max_fail_nodes": 1,
        "nodes_max_hops": 3,
    },
}

tab1, tab2 = st.tabs(["手工输入计算", "随机拓扑压测"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        text = st.text_area("拓扑 JSON 输入", value=json.dumps(sample, indent=2, ensure_ascii=False), height=460)
    with col2:
        st.markdown("### 输入说明")
        st.write("- reliability 支持 0~1 或百分数(如95)")
        st.write("- subset_nodes 可选")
        st.write("- subset_max_fail / max_fail_nodes / nodes_max_hops 可选")

    if st.button("计算可靠度", type="primary"):
        try:
            payload = json.loads(text)
            topo = Topology(
                nodes=[Node(**n) for n in payload.get("nodes", [])],
                edges=[Edge(**e) for e in payload.get("edges", [])],
                constraints=Constraints(**payload.get("constraints", {})),
            )
            rel, profile = service.calculate_with_profile(topo)
            st.success(f"可靠度结果: {rel:.12f}")
            st.metric("BDD 节点数", profile.bdd_nodes)
            st.json({
                "build_vars_ms": round(profile.build_vars_ms, 3),
                "build_constraints_ms": round(profile.build_constraints_ms, 3),
                "probability_ms": round(profile.probability_ms, 3),
                "total_ms": round(profile.total_ms, 3),
            })
        except Exception as e:
            st.error(f"计算失败: {e}")

with tab2:
    st.markdown("### 随机拓扑生成 + 性能测试")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        node_count = st.number_input("节点数", min_value=2, max_value=60, value=20)
    with c2:
        edge_count = st.number_input("边数", min_value=1, max_value=500, value=35)
    with c3:
        seed = st.number_input("随机种子", min_value=1, max_value=10_000_000, value=42)
    with c4:
        loops = st.number_input("重复次数", min_value=1, max_value=50, value=3)

    if st.button("生成并压测"):
        rows = []
        last_payload = None
        for i in range(int(loops)):
            payload = random_topology(int(node_count), int(edge_count), int(seed) + i)
            topo = Topology(
                nodes=[Node(**n) for n in payload.get("nodes", [])],
                edges=[Edge(**e) for e in payload.get("edges", [])],
                constraints=Constraints(**payload.get("constraints", {})),
            )
            rel, profile = service.calculate_with_profile(topo)
            rows.append({
                "run": i + 1,
                "reliability": rel,
                "bdd_nodes": profile.bdd_nodes,
                "build_vars_ms": profile.build_vars_ms,
                "build_constraints_ms": profile.build_constraints_ms,
                "probability_ms": profile.probability_ms,
                "total_ms": profile.total_ms,
            })
            last_payload = payload

        st.dataframe(rows, use_container_width=True)
        st.markdown("#### 最近一次随机拓扑 JSON")
        st.code(json.dumps(last_payload, indent=2, ensure_ascii=False), language="json")
