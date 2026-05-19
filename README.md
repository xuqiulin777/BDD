# Python BDD 网络可靠度计算工程（GUI版）

本项目提供桌面 GUI（Tkinter）用于：
- 图形化交互绘制网络拓扑（点击添加节点、两次点击添加边）
- 矩阵方式快速生成拓扑（例如 10×2，相邻节点自动连边）
- 计算网络可靠度并展示性能指标

## 运行方式

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python ui/gui_app.py
```

## GUI 核心功能

1. **交互式绘图**
   - “添加节点”模式：在画布点击添加节点
   - “添加边”模式：依次点击两个节点建立连边

2. **矩阵拓扑生成**
   - 输入行、列（如 10 和 2）
   - 点击“生成网格并连接相邻节点”
   - 自动创建规则拓扑并绘制

3. **可靠度计算**
   - 设置 `最大失效节点数`、`最大跳数`
   - 点击“计算可靠度”查看结果和分阶段耗时

## 主要文件

- `ui/gui_app.py`: Tkinter GUI 主程序
- `src/bdd_reliability/service.py`: 可靠度计算服务
- `src/bdd_reliability/robdd.py`: ROBDD 基础实现
- `src/bdd_reliability/model.py`: 数据模型
- `src/bdd_reliability/utils.py`: 工具函数与随机拓扑生成
