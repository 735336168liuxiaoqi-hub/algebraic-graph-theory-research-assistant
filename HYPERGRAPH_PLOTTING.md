# 超图绘图（v0.5）

桌面端通过“超图结构图”统一完成绘图和布局调整，结果页点击“调整布局”，不再单列交互布局入口。简单无向图可直接用二元边表输入，默认黑色实线；可保留孤立点、拖动、保存坐标及转普通图TikZ。自动布局不保证无交叉或标签无重叠。桌面JSON工具限制为128顶点、128边、2048次关联。

沿用原 `hypergraph_v22.sage` 的主要视觉约定：每条超边用不填充的闭合插值曲线表示，曲线穿过全部成员顶点。曲线内部的顶点不自动属于该超边；无顶点标记的曲线交叉不表示关联。二元边用普通线段表示。

TCB插值使用原包的默认参数 tension=0.5、continuity=0.5、bias=0。Python实现将相同的Hermite段转换为三次Bezier曲线，不需要Sage、WSL、SciPy或TeX。自动布局改为NetworkX关联图弹簧布局，并非复刻Sage的最终坐标。三点及以上共线时，为保持曲线可见，控制点略微弯曲；成员坐标不变。

支持一致和非一致超图、字符串/整数标签、孤立点及空超图。当前Hypergraph数据结构仍要求每边至少两个不同顶点、没有重复超边。不依赖张量计算。

```python
from graph_research import Hypergraph

h = Hypergraph([[0,1,2], [2,3], [3,4,5,6]], vertices=list(range(8)))
h.save_plot('nonuniform.png', edge_labels=True, legend=True)
h.save_plot('nonuniform.svg', edge_labels=True)
h.save_plot('nonuniform.pdf')

# plot返回Matplotlib Figure；graphplot返回绘图包装对象。
fig = h.plot(edge_labels=True)
fig.savefig('plot.png', dpi=200)
# 桌面Python环境中显式打开绘图窗口：h.show(edge_labels=True)

# 手工坐标必须覆盖全部顶点；保持用户坐标，不重新移动。
pos = {0:(-2,0),1:(-1,1),2:(0,0),3:(1,0),
       4:(2,1),5:(3,0),6:(2,-1),7:(0,1.7)}
h.set_pos(pos)
h.save_plot('manual.svg', edge_labels=True, legend=True)
```

参数包括 `pos`、`layout='spring'/'circular'`、`seed`、`iterations`、`vertex_labels`（布尔或标签字典）、`edge_labels`、`edge_colors`（按边顺序的颜色列表或边索引字典）、`edge_thickness`、`vertex_size`、`figsize`、`title`、`legend`、TCB参数以及已有Matplotlib `ax`。颜色复用时，超边线型会额外变化。

中文标签需要本机Matplotlib可用的中文字体，例如先设置 `matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']`。不依赖外部TeX。

```powershell
.\.venv\Scripts\python.exe -X utf8 examples/hypergraph_plot.py
.\.venv\Scripts\python.exe -X utf8 -m graph_research call hypergraph_plot '{"edges":[[0,1,2],[2,3],[3,4,5,6]],"vertices":[0,1,2,3,4,5,6,7]}'
```

模型工具返回PNG/SVG绝对路径、绘图坐标及超边成员表，输出到当前工作目录的`outputs/hypergraph-plots/`。最多128顶点、128边、2048个点边关联。文件路径由工具生成，模型不指定任意写入路径。

v0.6增加[拖动顶点的交互编辑器](HYPERGRAPH_EDITOR.md)，v0.7增加[简单图和超图的TikZ代码导出](TIKZ_EXPORT.md)。普通图的完整绘图接口、自动消除全部交叉尚未实现。复杂结构仍可能交叉或曲线靠近非成员顶点，可以手动调整并结合边标签与成员图例核对。该画法不保证任意超图都能无歧义地平面嵌入。

例图见 `outputs/hypergraph-plot-v05/gallery.png`；几何测试检查曲线插值成员顶点、闭合、不填充、非成员不被加入路径、共线退化、孤立点和文件导出。尚未声称与Sage逐像素一致。
