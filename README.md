# Python BDD 网络可靠度计算工程

这是一个可直接运行的 Python 工程，包含：
- 基于 ROBDD 的网络可靠度计算核心算法。
- 可视化 UI（Streamlit）用于输入拓扑、约束并输出可靠度。
- 随机拓扑生成与压测页面。
- 分阶段性能剖析（变量构建、约束构建、概率求值、总耗时、BDD 节点数）。

## 运行方式

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run ui/app.py
```

## UI 功能

### 1) 手工输入计算
- 输入 JSON 后点击“计算可靠度”
- 输出：可靠度 + profiling 指标

### 2) 随机拓扑压测
- 配置节点数、边数、随机种子、重复次数
- 点击“生成并压测”后输出多轮耗时与结果表
- 展示最近一次随机拓扑 JSON，便于复制到手工页复现

## 输入格式

- `nodes`: `[{id, reliability}]`
- `edges`: `[{id, source, target, reliability}]`
- `constraints`:
  - `subset_nodes`
  - `subset_max_fail`
  - `max_fail_nodes`
  - `nodes_max_hops`

`reliability` 支持 0~1 或百分比（如 `95`）。

## 核心文件

- `src/bdd_reliability/robdd.py`: ROBDD 引擎（唯一表、apply、概率求值）
- `src/bdd_reliability/service.py`: 网络可靠度建模（约束 + 连通性 + 概率 + profiling）
- `src/bdd_reliability/utils.py`: 随机拓扑生成、profiling 数据结构
- `ui/app.py`: 图形化输入与压测页面
