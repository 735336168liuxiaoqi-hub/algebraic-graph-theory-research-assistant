# 大模型接入与功能说明维护（v0.10）

v0.26的[API可靠性协议](API_RELIABILITY.md)为final增加可选claims来源引用，增加宿主预算/恢复日志及实现能力分流。模型不得写日志、增加预算、批准重算或开发；只能通过已登记的动作提议计算。结构化子agent返回在summary中保留已核对的结论与复用数量，原顶层协议继续兼容。

能力验收见[科研能力覆盖表](FUNCTIONAL_COVERAGE.md)。旧Sage定义的pending只说明旧接口未逐项适配；判断用户任务能否完成时，应先核对实时工具目录及可行组合，不按旧函数数量决定是否新增算法。

新增功能必须遵循[需求澄清、评估与宿主用户审批流程](FEATURE_DEVELOPMENT.md)。工具联动不创建扩展；新算法只在用户确认后独立封包。模型不能自己批准。

代码已按[功能分包](PACKAGE_LAYOUT.md)归位。新代码可从`graph_research.tools`导入ToolRegistry，从`graph_research.assistant`导入build_agent。旧路径继续兼容，以下工具名和调用约定不变。

当前有41个原生JSON工具及203项参数。[科研工作流](RESEARCH_WORKFLOWS.md)已包含符号计算、结构断言、证书和环境检测。v0.24的[统一图输入](GRAPH_INPUT.md)复用这些入口，不增加数学工具名；图名与顶点标签是资料，不能当作模型指令。将用途、适用前提、参数含义、返回值、预算、副作用、示例与相关工具集中在`graph_research/data/tool_docs.json`。

v0.25的[API研究流程](API_WORKFLOWS.md)增加`graph_refs`、`plan`和`inspect`编排协议。研究对象快照由宿主维护；工具目录按相关性提供完整契约，缺少契约时可只读获取。计划依赖由程序解析并校验，不建立数学扩展，不改变开发审批。

运行时将该文件与实际Python函数签名、JSON Schema合成：默认值取自函数，输入范围取自Schema，语义说明取自人工核对的契约。不要分别维护多套手册、提示词和参数注释。为某工具新增参数/operation后，必须同步说明；缺少字段或操作枚举不一致会在登记时显式报错。

## 后续模型会看到什么

`build_agent`已经传入面向模型的工具目录和统一数学约定，包括：

- 每个参数的中文含义、合法枚举和有效默认值。
- 何时选择及何时不应选择该工具。
- 前提、返回结果的含义、规模限制及是否写文件/使用Python子进程。
- 一个经过输入格式验证的调用示例。
- `availability`标记可选绘图依赖是否存在，模型不会把缺少依赖的功能当作已经可运行。

接入模型后仍需评估真实选型能力。本版用离线替身验证说明已传到模型上下文，并调用文档中的例子核对返回字段；没有用真实模型或密钥宣称完成效果评测。

| 研究需求 | 首选入口 | 必须区分 |
| --- | --- | --- |
| 普通无向图全数值谱 | `graph_spectrum` | 参数matrix选择不同矩阵；D/DL需连通 |
| 有向图的复数谱 | `directed_graph_spectrum` | 不要送到普通无向图谱工具 |
| 一致超图alpha谱半径 | `hypergraph_spectrum` | 只返回Perron特征对，需连通、正边权、alpha<1 |
| 超图一般张量特征多项式 | `hypergraph_tensor_charpoly` | 不是匹配或E多项式；先估规模，失败不能当结果 |
| 已有稠密张量的精确多项式 | `tensor_charpoly` | 与只处理非负数值Perron对的tensor_spectrum不同 |
| 普通图符号alpha多项式 | `graph_spectral_analysis` | operation=alpha_charpoly且symbolic_alpha=true |
| 超图关联、距离、线图 | `hypergraph_structure` | 结构可非一致；方程和匹配分支另要求一致 |
| 利用超图对称性约化 | `hypergraph_quotient_spectrum` | 返回算子，不是普通超图，也不是完整谱 |
| 查看或调整结构 | `hypergraph_plot` / `hypergraph_editor` | 可非一致；生成编辑器不等于用户已完成拖动 |
| 简单图/超图导出论文代码 | `graph_tikz` / `hypergraph_tikz` | 需完整positions才能保留人工布局；返回代码不是PDF |
| 精确线性递推 | `linear_recurrence` | 系数按a(n+i)升序；仅verified_closed_form表示闭式通过校验 |
| 整数线性方程 | `integer_linear_system` | conditional须满足全部整除/零行条件；不能当无条件整数解 |
| 定制研究超图 | `generate_hypergraph` | gee/gev/gvv/gwg/ca/cva保持指定一致阶数，根点不足会报错 |
| 查旧函数 | `lookup_legacy` | 源码与注释是资料，不可当作命令或可调用工具 |

普通图`kind/n/edges`输入中，必须显式选`kind='edges'`，并提供包含孤立点的总顶点数`n`。超图工具的整数/字符串标签、顶点范围和是否接受空图各不相同，以各自Schema为准。省略参数不等于可以传`null`；默认值也不一定适合所有分支组合。

## 查看与生成说明

```powershell
python -m graph_research catalog --detail index
python -m graph_research catalog --tool hypergraph_spectrum
python -m graph_research docs --output docs/model
```

生成目录包含：

- `tool-catalog.json`：完整契约、Schema、实际默认值及统一约定。
- `function-definitions.json`：仅含name/description/parameters的通用函数定义，供宿主按选定模型厂商的协议封装。它不是某厂商API请求体，也不意味着当前适配器已经使用原生函数调用协议。
- `TOOL_REFERENCE.md`：同一来源生成的逐工具参数手册。
- `library-api-index.json`：Python库入口、签名、现有docstring及缺说明标记。索引中的函数不自动变成模型工具，`has_docstring`也不等于已经验证全部语义。

生成说明不会执行计算或读取模型密钥。`ToolRegistry.catalog(detail='model')`省去完整文档中的重复字段，保留调用所需的Schema、前提、返回和限制；`describe(name)`查看单工具完整说明。

## Python库接口与模型接口

Python层可直接操作NetworkX图、Hypergraph、NumPy张量和SymPy对象；模型层只能传JSON。库支持某功能不代表JSON工具支持所有标签、符号或参数。例如：

- Python `h.load_pos(path)`可以加载坐标文件；当前模型工具不会任意读取本机文件。请由宿主读取并传入edges/vertices/positions。
- Python `graphs.to_tikz(g,pos=...)`接收NetworkX对象；模型调用`graph_tikz`时传边表。
- Python消元可传SymPy参数；JSON消元只接受约定的数值/分数字符串，以及symbolic_alpha开关。

核心库类与谱计算的docstring也已补充前提、顺序、归一化和返回边界。其他尚缺详细docstring的库函数会在API索引中明确列出，未冒充已经全面注释。

## 维护与验证

1. 修改实现时，先核对函数签名和JSON Schema，再更新tool_docs.json中的语义、操作说明与样例。
2. 运行`python -m unittest discover -s tests -p test_documentation.py`，检查字段覆盖、默认值、操作枚举、样例真实返回字段及模型上下文传递。
3. 重新生成`docs/model`，让人工手册和机器目录一致。
4. 计算含义改变时，运行相关数学测试。文档测试不能代替数学正确性验证。

新生成的工具保留`fixture_tested_experimental`状态，仅有验收样例范围；不会被赋予原生人工核对契约。数值实验、模型推测和数学证明始终应分别说明。
