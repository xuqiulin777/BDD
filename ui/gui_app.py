import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from bdd_reliability.model import Constraints, Edge, Node, Topology
from bdd_reliability.service import ReliabilityService


class TopologyGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("网络可靠度计算 GUI")
        self.geometry("1180x800")

        self.service = ReliabilityService()
        self.nodes = []
        self.edges = []
        self.node_pos = {}
        self.node_id_seed = 1
        self.edge_id_seed = 1
        self.mode = tk.StringVar(value="add_node")
        self.pending_edge_node = None

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=8)

        ttk.Radiobutton(top, text="添加节点", variable=self.mode, value="add_node").pack(side=tk.LEFT)
        ttk.Radiobutton(top, text="添加边", variable=self.mode, value="add_edge").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(top, text="删除节点", variable=self.mode, value="delete_node").pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(top, text="删除边", variable=self.mode, value="delete_edge").pack(side=tk.LEFT, padx=8)

        ttk.Label(top, text="节点可靠度").pack(side=tk.LEFT, padx=(20, 4))
        self.node_rel = ttk.Entry(top, width=8)
        self.node_rel.insert(0, "0.99")
        self.node_rel.pack(side=tk.LEFT)

        ttk.Label(top, text="节点类型").pack(side=tk.LEFT, padx=(10, 4))
        self.node_type = ttk.Combobox(top, width=8, state="readonly", values=["normal", "key"])
        self.node_type.set("normal")
        self.node_type.pack(side=tk.LEFT)

        ttk.Label(top, text="边可靠度").pack(side=tk.LEFT, padx=(10, 4))
        self.edge_rel = ttk.Entry(top, width=8)
        self.edge_rel.insert(0, "0.995")
        self.edge_rel.pack(side=tk.LEFT)

        ttk.Button(top, text="清空", command=self.reset_graph).pack(side=tk.RIGHT)

        gen = ttk.Frame(self)
        gen.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(gen, text="矩阵生成: 行").pack(side=tk.LEFT)
        self.rows_entry = ttk.Entry(gen, width=6)
        self.rows_entry.insert(0, "10")
        self.rows_entry.pack(side=tk.LEFT, padx=4)
        ttk.Label(gen, text="列").pack(side=tk.LEFT)
        self.cols_entry = ttk.Entry(gen, width=6)
        self.cols_entry.insert(0, "2")
        self.cols_entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(gen, text="生成网格并连接相邻节点", command=self.generate_grid).pack(side=tk.LEFT, padx=8)

        cons = ttk.Frame(self)
        cons.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(cons, text="全网最大失效节点数(必填)").pack(side=tk.LEFT)
        self.max_fail_entry = ttk.Entry(cons, width=8)
        self.max_fail_entry.insert(0, "1")
        self.max_fail_entry.pack(side=tk.LEFT, padx=4)

        ttk.Label(cons, text="关键节点最大失效数(可选)").pack(side=tk.LEFT)
        self.key_fail_entry = ttk.Entry(cons, width=8)
        self.key_fail_entry.insert(0, "")
        self.key_fail_entry.pack(side=tk.LEFT, padx=4)

        ttk.Label(cons, text="最大跳数(可选)").pack(side=tk.LEFT)
        self.hops_entry = ttk.Entry(cons, width=8)
        self.hops_entry.insert(0, "")
        self.hops_entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(cons, text="计算可靠度", command=self.compute).pack(side=tk.LEFT, padx=10)

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(body, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        right = ttk.Frame(body, width=320)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Label(right, text="结果 / 说明").pack(anchor="w")
        self.result_text = tk.Text(right, height=24, width=40)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def reset_graph(self):
        self.nodes.clear()
        self.edges.clear()
        self.node_pos.clear()
        self.node_id_seed = 1
        self.edge_id_seed = 1
        self.pending_edge_node = None
        self.canvas.delete("all")

    def generate_grid(self):
        try:
            rows = int(self.rows_entry.get())
            cols = int(self.cols_entry.get())
            node_rel = float(self.node_rel.get())
            edge_rel = float(self.edge_rel.get())
        except ValueError:
            messagebox.showerror("错误", "行列/可靠度请输入合法数字")
            return
        if rows <= 0 or cols <= 0:
            messagebox.showerror("错误", "行列必须大于0")
            return

        self.reset_graph()
        spacing_x, spacing_y = 70, 55
        start_x, start_y = 50, 50

        for r in range(rows):
            for c in range(cols):
                nid = f"N{self.node_id_seed}"
                self.node_id_seed += 1
                x = start_x + c * spacing_x
                y = start_y + r * spacing_y
                node_type = "key" if c == 0 else "normal"
                self.nodes.append(Node(id=nid, reliability=node_rel, node_type=node_type))
                self.node_pos[nid] = (x, y)

        index = lambda rr, cc: rr * cols + cc
        for r in range(rows):
            for c in range(cols):
                cur = self.nodes[index(r, c)].id
                if c + 1 < cols:
                    self._add_edge(cur, self.nodes[index(r, c + 1)].id, edge_rel)
                if r + 1 < rows:
                    self._add_edge(cur, self.nodes[index(r + 1, c)].id, edge_rel)

        self.redraw()

    def _add_edge(self, s, t, rel):
        if self._edge_exists(s, t):
            return
        eid = f"e{self.edge_id_seed}"
        self.edge_id_seed += 1
        self.edges.append(Edge(id=eid, source=s, target=t, reliability=rel))

    def _edge_exists(self, s, t):
        return any((e.source == s and e.target == t) or (e.source == t and e.target == s) for e in self.edges)

    def on_canvas_click(self, event):
        mode = self.mode.get()
        if mode == "add_node":
            self._handle_add_node(event)
        elif mode == "add_edge":
            self._handle_add_edge(event)
        elif mode == "delete_node":
            self._handle_delete_node(event)
        elif mode == "delete_edge":
            self._handle_delete_edge(event)

    def _handle_add_node(self, event):
        try:
            rel = float(self.node_rel.get())
        except ValueError:
            messagebox.showerror("错误", "节点可靠度请输入数字")
            return
        nid = f"N{self.node_id_seed}"
        self.node_id_seed += 1
        self.nodes.append(Node(id=nid, reliability=rel, node_type=self.node_type.get()))
        self.node_pos[nid] = (event.x, event.y)
        self.redraw()

    def _handle_add_edge(self, event):
        hit = self._find_node_at(event.x, event.y)
        if not hit:
            return
        if self.pending_edge_node is None:
            self.pending_edge_node = hit
            return
        if hit != self.pending_edge_node:
            try:
                edge_rel = float(self.edge_rel.get())
            except ValueError:
                messagebox.showerror("错误", "边可靠度请输入数字")
                return
            self._add_edge(self.pending_edge_node, hit, edge_rel)
        self.pending_edge_node = None
        self.redraw()

    def _handle_delete_node(self, event):
        hit = self._find_node_at(event.x, event.y)
        if not hit:
            return
        self.nodes = [n for n in self.nodes if n.id != hit]
        self.edges = [e for e in self.edges if e.source != hit and e.target != hit]
        self.node_pos.pop(hit, None)
        if self.pending_edge_node == hit:
            self.pending_edge_node = None
        self.redraw()

    def _handle_delete_edge(self, event):
        edge_id = self._find_edge_at(event.x, event.y)
        if edge_id is None:
            return
        self.edges = [e for e in self.edges if e.id != edge_id]
        self.redraw()

    def _find_node_at(self, x, y):
        for nid, (nx, ny) in self.node_pos.items():
            if (nx - x) ** 2 + (ny - y) ** 2 <= 12 ** 2:
                return nid
        return None

    def _find_edge_at(self, x, y):
        threshold = 8.0
        for e in self.edges:
            if e.source not in self.node_pos or e.target not in self.node_pos:
                continue
            x1, y1 = self.node_pos[e.source]
            x2, y2 = self.node_pos[e.target]
            dist = self._point_to_segment_distance(x, y, x1, y1, x2, y2)
            if dist <= threshold:
                return e.id
        return None

    @staticmethod
    def _point_to_segment_distance(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = ((px - x1) * dx + (py - y1) * dy) / float(dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x, proj_y = x1 + t * dx, y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

    def redraw(self):
        self.canvas.delete("all")
        for e in self.edges:
            if e.source in self.node_pos and e.target in self.node_pos:
                x1, y1 = self.node_pos[e.source]
                x2, y2 = self.node_pos[e.target]
                self.canvas.create_line(x1, y1, x2, y2, fill="#888", width=2)
        for n in self.nodes:
            x, y = self.node_pos[n.id]
            fill = "#ffb3b3" if n.node_type == "key" else "#5aa9ff"
            self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, fill=fill, outline="#1e4b7a")
            self.canvas.create_text(x, y - 18, text=f"{n.id}({n.node_type[0]})", font=("Arial", 9))

    def compute(self):
        try:
            if not self.max_fail_entry.get().strip():
                raise ValueError("全网最大失效节点数为必填项")
            max_fail = int(self.max_fail_entry.get())
            key_fail = int(self.key_fail_entry.get()) if self.key_fail_entry.get().strip() else None
            hops = int(self.hops_entry.get()) if self.hops_entry.get().strip() else None
            key_nodes = [n.id for n in self.nodes if n.node_type == "key"]
            topo = Topology(
                nodes=self.nodes,
                edges=self.edges,
                constraints=Constraints(
                    max_fail_nodes=max_fail,
                    nodes_max_hops=hops,
                    subset_nodes=key_nodes,
                    subset_max_fail=key_fail,
                ),
            )
            result, profile = self.service.calculate_with_profile(topo)
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, f"关键节点数: {len(key_nodes)}\n")
            self.result_text.insert(tk.END, f"关键节点失效上限: {key_fail}\n")
            self.result_text.insert(tk.END, f"最大跳数: {hops}\n")
            self.result_text.insert(tk.END, f"全网最大失效节点数: {max_fail}\n")
            self.result_text.insert(tk.END, f"可靠度: {result:.8f}\n")
            self.result_text.insert(tk.END, f"BDD节点数: {profile.bdd_nodes}\n")
            self.result_text.insert(tk.END, f"变量构建(ms): {profile.build_vars_ms:.2f}\n")
            self.result_text.insert(tk.END, f"约束构建(ms): {profile.build_constraints_ms:.2f}\n")
            self.result_text.insert(tk.END, f"概率计算(ms): {profile.probability_ms:.2f}\n")
            self.result_text.insert(tk.END, f"总耗时(ms): {profile.total_ms:.2f}\n")
        except Exception as e:
            messagebox.showerror("计算失败", str(e))


if __name__ == "__main__":
    app = TopologyGui()
    app.mainloop()
