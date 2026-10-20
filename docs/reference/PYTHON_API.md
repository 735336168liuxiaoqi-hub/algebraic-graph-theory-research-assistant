# Python接口与工具入口

当前复用现有Python实现及NetworkX、SymPy、Matplotlib，不新增依赖。当前工作版共43个内置工具、238项顶层参数；桌面显示37项，绘图、布局与LaTeX整合到对应图的操作面板。所有入口共用受保护计算、中文契约、输入示例、悬停说明和结果打包。

## 桌面使用

重新打开项目的“algebraic graph theory research assistant.exe”，在“本地工具”中选择：

| 分类 | 入口 | 已接通能力 |
| --- | --- | --- |
| 组合与多项式 | 格路径与棋盘绘图 | 逐步格路径、按右移步序号生成路径、矩形、数值矩阵棋盘；导出PNG/SVG/PDF |
| 当前图或计算结果旁 | 绘图 / 布局 / LaTeX | 普通图与超图结构预览、拖动、坐标保存、图片及TikZ导出；普通图七种自动布局和坐标变换 |
| 组合与多项式 | 组合计算 | 新增棋盘车多项式，以及Cayley左乘/右乘/双侧选项 |
| 普通图 | 图结构变换 | 新增批量用图替换边、局部笛卡尔积；保留可联动的重新编号图描述 |

每个操作的输入方式及可导入例子见[输入手册](../OFFLINE_INPUTS.md)。切换操作后，按对应分支填写；不需要的可选字段留空。缺少可选绘图依赖时，界面给出[visual]安装提示，不会自动安装。

顶部“绘图与导出”可直接使用当前工具的图参数；结果上方“查看结构图”可立即预览普通图。统一面板保留孤立点、原标签及已有坐标，自动布局提供编号对照；导出后仍保留数学计算表单。操作详见[桌面说明](../../使用指南.md)。CLI/API/MCP仍按原工具名称调用。

## 模型与MCP

API对话、子agent和MCP的research_catalog会发现同一套工具，不需要另写API专用算法。现有进程需重启以加载本次源码，宿主应重新读取工具契约及schema_hash。固定运行副本仍使用其自身封存版本，不随工作目录更新。

调用`combinatorial_plot`：

```json
{"operation":"grid_path","steps":[1,0,1,0]}
```

0向上、1向右，从原点出发，上例终点[2,2]。等价输入是`{"operation":"lattice_path","total_steps":4,"right_steps":[0,2]}`，序号从0开始。

```json
{"operation":"chessboard","matrix":[[1,0,1],[0,1,0]],"row_labels":["下行","上行"],"column_labels":["甲","乙","丙"]}
```

棋盘按行输入，非零格着色；行号沿y轴自下向上、列号从左向右。标签是普通文本，不执行表达式。

调用`graph_layout`：

```json
{"operation":"spring","kind":"path","n":3,"positions":[{"vertex":0,"xy":[0,0]},{"vertex":1,"xy":[1,1]},{"vertex":2,"xy":[2,0]}],"fixed_vertices":[0,2]}
```

返回完整positions、graph_spec和坐标JSON文件；无重合坐标时另有PNG/SVG预览。模型可把positions和graph_spec.edges绑定到graph_tikz，批量联动见[任务文件](../../examples/library_entries/layout-to-tikz.mcp.json)。每个新请求请使用新的request_id；运行中的任务按task_id查询，不重复提交。

变换操作先等比例缩放并绕原点逆时针旋转angle度，最后平移offset。对齐只改选中顶点的对应坐标，其他顶点不动。固定弹簧布局必须提供全部初始坐标。

谱布局只用于可视化，不是同构证明。出现重合点时，原坐标仍被保存，preview_status为not_rendered，并给出warnings；不会自动扰动谱坐标。此时请更换布局或调整坐标后绘图。

调用`combinatorial_calculation`：

```json
{"operation":"rook_polynomial","board":[[1,1],[1,1]]}
```

返回车多项式`2*x**2 + 4*x + 1`，升幂系数[1,4,2]分别表示放置0、1、2个互不攻击车的方案数。1格可用、0格禁用；每维至多10。

```json
{"operation":"cayley_graph","generators":[[1,0,2],[1,2,0]],"side":"twosided"}
```

side取right、left、twosided，分别为g→g·s、g→s·g和两者的并；重复弧合并、自环省去，原默认right保持不变。

调用`graph_edit`：

```json
{"operation":"replace_edges","kind":"path","n":3,"edit_edges":[[0,1],[1,2]],"replacement":{"kind":"path","n":3},"endpoints":[0,2]}
```

每条边使用独立替换图副本，得到五点路径，原图孤立点保留。

```json
{"operation":"partial_product","kind":"path","n":3,"vertices":[1],"replacement":{"kind":"path","n":2}}
```

选定顶点诱导子图与replacement作笛卡尔积，再把积顶点接回原顶点的外部邻点。后续谱计算使用graph_spec；不要把复合标签直接送入只接受整数编号的工具。

## 接口边界

不开放任意Python回调、对象显示钩子或非标准循环指标编码为模型工具。超图布局继续使用现有结构图与交互编辑器；既有矩阵和符号计算复用现有入口。完整隐式三维绘图、TeX编译及Windows安装器不在当前范围。

## 如何选择库接口

已登记工具可用 `ToolRegistry.describe(name)` 读取契约、`ToolRegistry.call(name, arguments)` 调用；桌面、API和MCP使用同一工具定义。数学库还可直接导入NetworkX、SymPy与本包模块，但不自动拥有任务预算、审批和成果管理语义。

完整[Python接口索引](../model/library-api-index.json)区分model_callable状态；[工具契约](../model/TOOL_REFERENCE.md)列出模型可调用范围。直接库调用的资源控制由开发者负责，集成应用通常应使用既有受保护执行入口。
