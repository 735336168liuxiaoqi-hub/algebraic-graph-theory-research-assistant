# 简单图与超图转LaTeX/TikZ（v0.7）

v0.32另增[鼠标论文示意图](SCHEMATIC_DRAWING.md)，用于带省略、花括号和符号路长的图族表示。本文的完整结构导出保留，默认行为未改变。

输出标准TikZ，不照搬旧Sage接口或输出格式。支持普通无向简单图、一致或非一致超图，以及孤立点和空图。导出代码只需已有Python依赖，不需要Sage、WSL或本机TeX；编译代码时才需要LaTeX环境。

## 编辑器中导出

调整好布局后点击“导出LaTeX”，可以预览、复制代码或下载`.tex`。

- 勾选“完整文档”：生成可单独编译的文件。
- 取消“完整文档”：生成`tikzpicture`片段，可粘贴进论文；论文导言区添加`\usepackage{tikz}`。
- 可隐藏顶点标签；超边编号跟随编辑器的“显示超边编号”设置。
- 保留当前全部顶点和超边的布局，不受画布平移、缩放或临时高亮影响。不会重新执行自动布局。
- 同样支持全部边大小为2的简单图。下载文件名可自行修改。

输出直接记录三次Bezier控制点；不依赖`hobby`库，不再用另一种平滑算法近似已有曲线。默认均匀缩放、平移到最长控制点跨度10cm，保持相对位置、比例及曲线形状。字体与线宽采用适合论文的TikZ样式，不承诺浏览器与TeX像素一致。

## 普通简单图：NetworkX接口

```python
import networkx as nx
from graph_research import graphs

g = nx.cycle_graph(5)
g.add_node('isolated')
pos = {0:(0,1), 1:(1,.3), 2:(.6,-1),
       3:(-.6,-1), 4:(-1,.3), 'isolated':(2,0)}

code = graphs.to_tikz(g, pos=pos)  # tikzpicture片段，默认黑色直线边
graphs.save_tikz(g, 'simple-graph.tex', pos=pos)  # 完整文档
graphs.save_tikz(g, 'figure.tex', pos=pos, standalone=False)
```

不传`pos`时，优先读取`g.graph['pos']`，否则自动生成坐标。此接口支持无自环、无重边的普通图；有向、负/复权图保留箭头与原权重。绘图样式及完整图对象入口见[本轮修复](GRAPH_OUTPUT_FIXES.md)。

## 超图：保留编辑器的坐标

```python
from graph_research import Hypergraph

h = Hypergraph.from_layout('保存的布局.json')
print(h.to_tikz(edge_labels=True))
h.save_tikz('hypergraph.tex', edge_labels=True)
h.save_tikz('figure.tex', standalone=False, edge_labels=True)

# 也可以直接构造和指定坐标：
h = Hypergraph([[0,1,2], [2,3]])
h.set_pos({0:(0,0), 1:(1,1), 2:(2,0), 3:(3,0)})
h.save_tikz('literal-coordinates.tex', normalize=False)
```

通用参数包括`standalone`、`pos`、`vertex_labels`（布尔或标签字典）、`edge_labels`、`edge_colors`、`normalize`、`size_cm`、`seed`和TCB参数。`normalize=False`在输出中使用原坐标（单位cm），但须适合TeX尺寸，绝对坐标超过100cm时明确拒绝；默认归一化可导出原坐标很大的布局。

顶点名以`v0,v1,...`作为TikZ内部标识，显示标签与标识分离。文本中的`_`、`%`、`&`、`$`、花括号和反斜杠会转义，避免改变代码语义。若需要数学下标，可在导出后把相应节点文本改成如`$v_1$`。中文标签的完整文档自动加载`ctex`，使用XeLaTeX编译；普通数字标签可用pdfLaTeX。任意Unicode字符的显示还取决于所选字体。

## 命令行与模型工具

```powershell
# 编辑器保存的布局JSON，导出完整文档：
python -m graph_research latex 保存的布局.json --output hypergraph.tex --edge-labels

# 简单图JSON格式同样是edges和可选vertices：
python -m graph_research latex examples/simple_graph.json --simple-graph --output graph.tex

# 论文片段：
python -m graph_research latex 保存的布局.json --fragment --output figure.tex
```

模型可分别调用`graph_tikz`和`hypergraph_tikz`，传入边、顶点以及可选的`positions=[{'vertex':标签,'xy':[x,y]},...]`。工具返回完整文档和片段文件路径；片段超过60000字符时只返回路径，不截断文件内容。

## 已验证

普通简单图、非一致超图、中文标签及浏览器下载的完整文档已通过编译。测试检查Bezier控制点与Python绘图一致、浏览器/Python两种导出的几何一致、标签转义、孤立点、空图、极端坐标归一化及两种模型工具。

具体例子保存在`outputs/tikz-v07/`。编译不是工具库自动执行的一步，也不代表所有外部论文模板、字体或用户手改后的代码均已验证。
