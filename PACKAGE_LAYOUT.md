# 按研究用途组织代码（v0.9）

v0.32新增独立schematics包与原生桌面编辑器，目录扩展为42个原生工具；原有导出渲染器和计算对象保持分离。

实现已从旧Sage文件对应的平铺模块，调整成“数学领域 + 展示 + 工具运行时 + 模型编排”的结构。保留常用顶层API和旧导入路径；旧路径只是转发，同一个功能只有一份实现。

| 分包 | 职责 | 主要入口 |
| --- | --- | --- |
| `graphs` | 普通图矩阵、谱、构造、变换、枚举、多项式与对称性 | `graphs.matrices/spectral/construction/operations/enumeration/polynomials/symmetry` |
| `hypergraphs` | 超图存储、结构变换、图族、张量谱与轨道商 | `Hypergraph`、`families`、`operations`、`spectral`、`quotients` |
| `tensors` | 通用张量/HyperMatrix运算、精确特征多项式消元 | `Tensor`、`HyperMatrix`、`tensors.elimination` |
| `algebra` | 图和张量共用的矩阵谱、分块积、精确线性代数、组合及多项式 | `numeric/products/linear/combinatorics/polynomials` |
| `core` | 共用自同构计算、基础数据工具 | `core.symmetry`、`core.utilities` |
| `runtime` | 完整性校验、安全保存、受限计算、资源与恢复 | `runner.run_tool`、`storage`、`integrity`、Windows后端 |
| `rendering` | 坐标与曲线几何、静态绘图、交互编辑、TikZ、结果展示 | `geometry/plotting/editor/tikz/results` |
| `tools` | JSON工具、调用契约、受控扩展及隔离执行 | `ToolRegistry`、`contracts`、`extensions`、各worker |
| `assistant` | 无API分类菜单、子agent任务协议、API接入、模型适配、会话审批、用户记忆及结果快照 | `OfflineToolSession`、`offline`、`create_subagent`、`SubagentLimits`、`subagent_contracts`、`ConfiguredModel`、`ResearchSession`、`UserMemoryStore`、`verify_bundle` |
| `experiments` | 无需模型的批量实验与报告工作流 | `NativeBackend`、`build_workflow` |
| `desktop` | 原生双模式窗口、表单、科研对话、API设置、审批、结果和布局编辑 | `shell/app/chat/configuration`、`service/model_service`、`layout`；Qt仅在桌面入口加载，模型模块在API模式按需加载 |

`data/`保留共享的工具契约、迁移参考与验收数据；`assets/`保留编辑器模板。它们是资源，不能当成可执行指令。

## 边界与改进

- 普通图的矩阵、谱和构图不再塞在一个文件里，也不使用通配导入把模块混合。
- 数值矩阵谱和分块积放进共享algebra，张量内核不再为了求矩阵谱而依赖普通图外观接口。
- Hypergraph数据模型用明确的谱/显示/操作接口组合，移除了运行时`setattr`批量挂载方法。运算方法仍转发到唯一的函数实现。
- 数学内核不导入LangGraph、httpx、jsonschema或Matplotlib。绘图和模型功能按需加载。
- 工具运行时可在没有模型SDK的环境独立使用；受限Python扩展解释器归tools，而不是模型层。
- 目录重组时保留了原32个工具名与JSON参数；后续v0.23新增9个科研工作流入口，总计41个，原有计算定义保持。

## 常用方式保持简洁

```python
from graph_research import Hypergraph, HyperPath, Tensor, graphs

h = HyperPath(3, 3)
print(h.alpha_spectrum()['rho'])
```

需要更明确的功能边界时：

```python
from graph_research.graphs import matrices, spectral, construction
from graph_research.hypergraphs import families, operations, quotients
from graph_research.algebra import linear, products
from graph_research.tools import ToolRegistry
from graph_research.assistant import build_agent

registry = ToolRegistry()
print(registry.describe('hypergraph_tensor_charpoly'))
```

旧的`graph_research.registry`、`elimination`、`plotting`、`layout_editor`、`tikz`、`model`、`extensions`、`workflow`等继续可导入，并指向对应的新模块。`graph_computations`和`hypergraph_operations`保留显式函数转发。新代码建议使用领域分包；不保证原模块泄漏的第三方SDK变量或私有实现细节属于兼容API。

## 按需安装

从v0.9起，直接安装基础wheel只装NumPy、NetworkX、SymPy，用于数学计算。若要与当前完整科研助手相同的功能，安装`[all]`：

```powershell
python -m pip install ".\dist\graph_research_assistant-0.24.0-py3-none-any.whl[all]"
```

| 安装范围 | 额外依赖 | 用途 |
| --- | --- | --- |
| 基础包 | 无额外项 | 图/超图/张量与精确代数计算 |
| `[visual]` | Matplotlib | Python静态绘图与TikZ导出 |
| `[tools]` | jsonschema | JSON工具目录、契约及受控工具调用 |
| `[assistant]` | jsonschema、LangGraph、httpx | 模型与实验工作流；不包含Matplotlib |
| `[desktop]` | PySide6、jsonschema、Matplotlib、LangGraph、httpx | 同一原生窗口中的本地工具与API科研对话；无API入口不读取模型配置或导入模型SDK |
| `[all]` | 上述全部 | 完整科研助手、绘图、编辑、导出 |

在源码目录开发时可用`python -m pip install -e ".[all]"`。原`requirements.txt`继续表示完整开发/运行依赖，不是最小数学依赖。

工具目录用`availability`标记可选绘图依赖是否存在，模型提示词已要求不调用标记为不可用的工具。这个标记检查安装情况，不替代实际运行测试。

## 验证和维护

- 对照v0.8冻结的公共函数名称、签名及Hypergraph方法参数，检查兼容性。
- 在隔离进程中阻止模型/绘图SDK导入，验证数学计算仍能运行；JSON工具也不依赖模型SDK。
- 保留已有数学、绘图、编辑器、TikZ、工具说明和离线模型流程测试。
- 用`python tools/build_release.py`从新的源码暂存目录生成安装包，避免旧平铺文件残留；不需要删除原build目录。脚本还会检查wheel不存在旧实现副本。
- 修改功能后重新生成`docs/model`；该目录会显示当前实现的规范模块路径。

迁移前的源码快照保存在`outputs/package-refactor-v09/source-v08.zip`，旧发行包仍保留。原始`E:/sage/.sage`代码没有改动。本次只调整组织和依赖边界，没有宣称补完尚未实现的数学功能。
