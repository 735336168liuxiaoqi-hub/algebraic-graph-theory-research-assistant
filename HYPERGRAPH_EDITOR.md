# 拖动顶点的超图布局编辑器（v0.6）

支持一致和非一致超图。曲线沿用原Sage包的TCB参数，始终穿过成员顶点、不填充区域，二元边为线段。只需已有Python依赖及现代浏览器，无需模型、WSL、Sage或联网服务。

## 直接打开

双击已生成的 `outputs/hypergraph-editor-v06/editor.html` 即可离线编辑。也可在项目目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research edit examples/hypergraph_editor.json
```

命令会生成页面并尝试打开默认浏览器。`--no-open`仅生成文件，`--output 路径.html`指定输出位置。输入JSON使用`edges`、可选`vertices`（保留孤立点）及`weights`。也可直接传入先前保存的布局JSON，接着编辑。

## 操作

- 拖动黑色顶点：相关曲线立即更新。顶点拖动范围略大于显示圆点，便于选中。
- 点击顶点：左栏显示坐标，输入X/Y后点“应用坐标”精细调整。
- 拖动空白处平移；滚轮或右下角按钮缩放；“适应画布”重新居中。
- 点击超边成员列表突出显示该超边；不改变超边成员。
- “撤销/重做”支持最近100次坐标操作；快捷键Ctrl+Z、Ctrl+Shift+Z。
- “圆形布局”和“恢复初始”均可撤销。“恢复初始”指打开页面时的坐标。
- “保存坐标”（Ctrl+S）通过浏览器下载`hypergraph-layout.json`，位置以浏览器下载设置为准。浏览器可能给重名文件加编号；点击保存表示已发起下载，不代表直接覆盖Python文件。
- “导入坐标”选择已保存JSON，校验顶点和超边结构一致后加载；错误文件不会修改当前图。
- “导出SVG”下载当前视图的矢量图。先点“适应画布”可避免导出时图形位于视野外。
- v0.7新增“导出LaTeX”：预览、复制或下载当前完整布局的TikZ代码，可选择论文片段或完整文档。简单图也支持，详细参数见[TIKZ_EXPORT.md](TIKZ_EXPORT.md)。

页面中未保存的修改在关闭时会触发浏览器提醒；编辑页面自身不会自动重写。坐标导入后仍可撤销。缩放/平移是视图操作，不改变或保存数学坐标。

## 与Python科研计算衔接

```python
from graph_research import Hypergraph

h = Hypergraph([[0,1,2], [2,3], [3,4,5,6]], vertices=list(range(8)))
h.edit_layout('我的超图.html', open_browser=True)

# 在浏览器拖动并保存JSON后，使用实际下载路径加载：
h.load_pos(r'<LOCAL_PATH>
print(h.get_pos())
h.save_plot('调整后的图.png', edge_labels=True, legend=True)
h.save_plot('调整后的图.pdf', edge_labels=True)
h.save_pos('已确认布局.json')

# 也可从文件恢复超图结构、正边权与坐标，不必重新写超边列表：
restored = Hypergraph.from_layout('已确认布局.json')
restored.edit_layout('继续调整.html')
```

保存格式保留整数/字符串标签的类型区别（例如`1`和`'1'`）、超边成员、正边权及孤立点。边以顶点索引引用。为保证浏览器无损往返，编辑器接受字符串及绝对值≤2^53−1的整数标签，坐标绝对值≤10^9；不支持任意Python对象标签。坐标文件上限2MB。

同一图的顶点/边顺序不同也可加载；顶点标签集合与超边集合必须一致。`h.load_pos`仅更新坐标，不改原图权重或结构；`Hypergraph.from_layout`才从文件重建结构和边权。

模型工具`hypergraph_editor`接收超边列表并返回离线HTML路径，最多128顶点、128边、2048个点边关联。编辑是人工交互，尚不通过模型自动观察用户拖动结果；保存JSON再加载即可交给后续计算。

## 验证与边界

浏览器实际验证拖动、曲线更新、撤销/重做、数值编辑、JSON下载、重新导入及SVG下载；下载文件已加载回Python并导出静态图。开发测试还检查浏览器与Python的TCB控制点一致、坐标往返、拓扑不匹配拒绝、混合标签、孤立点、空图和标签转义。

布局变化后，曲线按顶点相对中心的角度重新排序，因此顶点穿越时曲线形状可能改变；成员不会改变。复杂结构的交叉、曲线恰好经过非成员顶点等仍需要人工调整。当前不支持新增/删除超边、单独拖动曲线控制点或自动保证无交叉；这是布局编辑器。
