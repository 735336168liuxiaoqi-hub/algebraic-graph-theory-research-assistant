# 旧Sage接口追溯台账（v0.23）

验收标准见[科研能力覆盖表](FUNCTIONAL_COVERAGE.md)：整体科研用途能够完成即可，不要求逐项迁移旧函数。以下仅保留源码追溯，不作为功能缺口数量或开发待办。

追溯统计：原有180条待适配定义；补齐/复用53条，并修正3条旧目录误判，现有130条旧定义尚未逐项适配。这不等于仍缺130项科研功能。
定义记录包括类、方法及两份超图文件中的同用途定义，不等于独立算法数。GraphTheory1.sage的165条完整重复定义单独记录，不算剩余功能。

本批仅复用现有NetworkX、SymPy、NumPy及可选Matplotlib，没有新增安装依赖。详细新接口、调用示例与限制见[替代功能说明](PACKAGE_REPLACEMENTS.md)。

## 尚未逐项兼容的旧接口（仅供追溯）


### myCombinatorics.sage（13条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `my_print`（65） | 生成求和式的LaTeX文本。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity`（68） | 保存求和项、上下限和求和值，逐步变换与展示求和恒等式。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.__init__`（69） | 求和恒等式容器的初始化；类尚未实现，旧目录误把None.__init__当作实现。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.__repr__`（76） | 求和恒等式对象的文本显示；类尚未实现，旧目录误把None.__repr__当作实现。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.__mul__`（78） | 给求和项乘因子并重新求和。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.action`（84） | 对求和项或等式两侧应用函数。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.subs`（94） | 代入符号并重新计算或同步变换两侧。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.factor`（103） | 分解求和值。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.simplify`（106） | 简化求和项并重新求和。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.show1`（110） | 显示求和恒等式。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.actionlist`（112） | 记录一串变换的中间状态。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyIdentity.show`（118） | 显示求和值与未求值求和式。 | symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。 |
| `MyPowerSeries`（225） | 通过字符串求值将表达式转到幂级数环；原实现使用eval，应改用显式符号级数。 | symbolic_analysis已提供Taylor/Laurent局部展开、O项及截断式；不使用原eval和隐式幂级数环。 |

### MyTools.sage（2条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `l2math`（140） | 读取剪贴板中的整数LaTeX数组并转矩阵。 | 已有显式文本矩阵解析；原函数的自动读剪贴板和符号求值副作用未移植。 |
| `L2Math`（151） | 读取剪贴板并求值LaTeX数组的符号单元格。 | 已有显式文本矩阵解析；原函数的自动读剪贴板和符号求值副作用未移植。 |

### MyUtility.sage（22条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `Latex2Image`（9） | 调用TeX引擎把对象排版成PNG。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `Graph2Image`（17） | 通过TeX/TikZ渲染图像，依赖外部TeX环境。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `my_repr_html`（41） | 把Sage绘图转为嵌入PNG的HTML。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `Reshape`（83） | 按列数重排对象列表并补空格。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `Table`（153） | 混排图像、Pandas样式表和普通对象为HTML表格。 | 现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。 |
| `viewgraph`（170） | 输出交互图HTML并嵌入iframe。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `htmlview`（188） | 展示图与不变量的对照表。 | 现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。 |
| `showGA`（206） | 按网格批量展示图。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `latex_draw`（211） | 通过LaTeX生成多幅图并排展示。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `Graphics2Data`（232） | 把图、绘图对象或图片编码为PNG/HTML。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `graph_to_html`（282） | 将图绘成base64内嵌PNG的HTML。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `graphs_list_save`（305） | 批量把图编码为内嵌PNG，实际返回HTML片段列表。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `variable_name`（413） | 按对象身份在全局命名空间寻找变量名，结果不唯一。 | 对象可能有多个变量别名；现用显式名称，不承诺由对象唯一反查变量。 |
| `TCBSpline`（427） | 控制张力、连续性、偏置的插值样条类。 | 现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。 |
| `TCBSpline.__init__`（428） | 初始化TCB样条参数与控制点缓存；类尚未实现，旧目录误判此构造器可用。 | 现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。 |
| `TCBSpline._calc_tangents_kochanek_bartel`（436） | 计算TCB样条的入/出切向量。 | 现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。 |
| `TCBSpline._calc_tangents_catmull_rom`（464） | 计算Catmull–Rom切向量。 | 现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。 |
| `TCBSpline.interpolate`（484） | 采样开曲线或闭曲线的TCB插值点。 | 现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。 |
| `graphs_list_show`（561） | 带编号或名字批量展示图表。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `base64ToPng`（572） | 解码HTML中的base64图片并保存PNG。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `html_add`（581） | 连接两个HTML片段。 | 现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。 |
| `table_add`（588） | 按行拼接两个表格。 | 现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。 |

### Tensor.sage（1条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `Tensor.__call__`（294） | 原代码调用NumPy数组对象；该数组本身不可调用。现有Tensor方括号索引已可取元素。 | 原数组不可调用；现有Tensor方括号索引和array可取元素，不编造额外调用语义。 |

### GraphTheory.sage（31条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `plot_by_eigenvector`（401） | 用指定两个或三个特征向量的分量作为绘图坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `De_subdivide_claw`（611） | 对剖分并附叶后的多项式比值作对数积分，计算能量差及误差。 | 图能量差已可直接计算；graph_energy_study提供有限参数域的精确根区间比较及复核。不迁移旧积分路线，特定积分公式及无限域证明另议。 |
| `De_subdivide_edge`（634） | 剖分和删根后用多项式比值积分比较能量。 | 图能量差已可直接计算；graph_energy_study提供有限参数域的精确根区间比较及复核。不迁移旧积分路线，特定积分公式及无限域证明另议。 |
| `energy_polynomial`（709） | 对反转特征多项式作Coulson型积分求能量；需核对收敛与适用条件。 | 图能量差已可直接计算；graph_energy_study提供有限参数域的精确根区间比较及复核。不迁移旧积分路线，特定积分公式及无限域证明另议。 |
| `perm_block`（1470） | 根据已有分块交换矩阵块行和块列。 | 已有基础分块/商矩阵，block_matrix_analysis另提供统一精确入口；旧分块对象和个别归一化接口不逐项兼容。 |
| `slip_graph`（1671） | 在附接路不同位置粘合另一个图，生成滑移构图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `subdivide`（2168） | 给矩阵标注行列分块；不是图的边剖分。 | 已有基础分块/商矩阵，block_matrix_analysis另提供统一精确入口；旧分块对象和个别归一化接口不逐项兼容。 |
| `subdivide1`（2186） | 矩阵分块后求块和及归一化商矩阵，两个分支的sym含义不一致。 | 已有基础分块/商矩阵，block_matrix_analysis另提供统一精确入口；旧分块对象和个别归一化接口不逐项兼容。 |
| `add_blossom`（2244） | 在指定点附接双重边形成多重图花瓣；当前普通谱接口要求简单图。 | NetworkX多重图可表达；当前主要谱入口要求简单图，须另定自环/重边约定后接入。 |
| `gline_graph_forbidden_subgraphs`（2269） | 解码旧包给出的31个广义线图禁诱导子图。 | graph_class_certificate已提供≤10顶点的广义线图精确覆盖判定、正证书和可重放负证书；预算耗尽为未判定，不复刻旧禁图列表接口。 |
| `is_gline_graph`（2278） | 通过禁诱导子图判断广义线图，证书分支混用了普通线图根图，需单独修复。 | graph_class_certificate已提供≤10顶点的广义线图精确覆盖判定、正证书和可重放负证书；预算耗尽为未判定，不复刻旧禁图列表接口。 |
| `layout_Tree`（2404） | 按根与方向生成树的层次坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `ShiftPos`（2511） | 平移并分别缩放两个坐标轴。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Pos`（2524） | 生成、设置并保存顶点布局坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `VerticesLabel`（2543） | 设置顶点显示标签。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Init`（2553） | 初始化坐标、标签和标签偏移。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `local_spring`（2563） | 固定一部分坐标，对其他顶点作弹簧布局。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Rotate_Shift`（2604） | 让两组顶点重心连线转到目标方向，并平移指定原点。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `GraphPlot`（2812） | 合并边颜色、标签等选项并返回Sage绘图对象。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Plot`（2869） | 使用共享绘图选项画图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `plot_graph_with_labels`（2905） | 用特征向量分量生成顶点标签并画图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Set_Label_with_Eigenvector`（2947） | 设置特征向量顶点标签和规范化坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `plotbycycle`（3005） | 原函数忽略输入，画写死的二十面体图Hamilton圈布局。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Latex`（3016） | 按布局导出图的LaTeX/TikZ。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Graph2TeX`（3054） | 生成TeX并调用外部引擎渲染，现有TikZ导出仅覆盖源码部分。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `Merge_And_Append_Edge`（3206） | 合并边端点再加边，可能产生自环/多重边，需明确目标图模型。 | NetworkX多重图可表达；当前主要谱入口要求简单图，须另定自环/重边约定后接入。 |
| `GraphList2TeX`（3480） | 把多幅图排成带子图的TeX表格，另可预览/编译。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `GL2TeX`（3574） | 批量图排版、旋转与长表格TeX导出。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `align_HV`（3654） | 把选定顶点组分别对齐到水平线或竖直线。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `CenterPos`（3676） | 将布局以重心或指定点居中；原实现忽略c参数。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `rich_repr`（3697） | 根据Sage富显示管理器自动展示图像、LaTeX或文本。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |

### hypergraph_v2.sage（25条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `HyperG.edge_coloring`（257） | 当前只返回空字典，是未实现的着色占位。 | 原函数仅返回空字典；需明确着色定义并新增算法，不能把占位结果当已实现。 |
| `HyperG._spring_layout`（260） | 在点边关联二部图上计算弹簧布局。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.Pos`（265） | 缓存点边布局并更新超边中心。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.setLposDeg1`（283） | 根据样条切向量放置叶顶点标签；v22的后定义覆盖前定义且不保存结果。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.setLabPos`（313） | 配置顶点标签偏移并调用叶点标签放置。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG._rich_repr_`（556） | 连接Sage富显示管理器，自动显示超图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.Latex`（591） | 按保存坐标和显示标签导出超图TikZ。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG._latex_`（653） | Sage的LaTeX显示钩子。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot._repr_`（675） | 绘图对象的简短文本表示。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot.set_vertices`（686） | 更新顶点样式和标签绘制组件。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot.set_edges`（715） | 更新超边曲线、颜色、线型和标签组件。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `myreprhtml`（1083） | 规范化布局后输出超图HTML预览。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `getPath`（1097） | 沿指定方向追踪超图内部路，原循环缺少歧义与终止保护。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `list2dtopanda`（1116） | 把二维数据转换为带行列名的Pandas样式表。 | 现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。 |
| `get_components`（1127） | 抽取指定内部路及对应的赋权关联子矩阵，并展示表格。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `LinkG`（1578） | 用两条内部路在主超图上接入根超图；单根分支写死了顶点与路长。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `weighted_incidence_graph`（1670） | 画带归一化关联权的点边二部图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Rotate_Shift`（1736） | 让两组顶点重心连线转到目标方向，并平移指定原点。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Valleys`（1762） | 扫描旋转角度，寻找包围盒面积指标的局部极小值。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Rotate`（1790） | 旋转、缩放并居中超图坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Normalize_Pos`（1808） | 按包围盒指标的极小值选择绘图旋转方向。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Graph2TeX`（1820） | 生成TeX并调用外部引擎渲染，现有TikZ导出仅覆盖源码部分。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `HyperTree1`（1944） | 拼接四个基本分支与内部路的专门超树族。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `U1`（2067） | 由两个3一致松路与两条内部路构造的专门图族，使用固定顶点编号。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `U2`（2074） | 在三边3一致松路中加内部路的专门图族。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |

### hypergraph_v22.sage（27条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `HyperG.edge_coloring`（287） | 当前只返回空字典，是未实现的着色占位。 | 原函数仅返回空字典；需明确着色定义并新增算法，不能把占位结果当已实现。 |
| `HyperG._spring_layout`（292） | 在点边关联二部图上计算弹簧布局。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.Pos`（297） | 缓存点边布局并更新超边中心。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.setLposDeg1`（319） | 根据样条切向量放置叶顶点标签；v22的后定义覆盖前定义且不保存结果。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.setLposDeg1`（341） | 根据样条切向量放置叶顶点标签；v22的后定义覆盖前定义且不保存结果。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.setLabPos`（350） | 配置顶点标签偏移并调用叶点标签放置。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG._rich_repr_`（612） | 连接Sage富显示管理器，自动显示超图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG.Latex`（647） | 按保存坐标和显示标签导出超图TikZ。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperG._latex_`（710） | Sage的LaTeX显示钩子。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot._repr_`（732） | 绘图对象的简短文本表示。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot.set_vertices`（743） | 更新顶点样式和标签绘制组件。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `HyperGraphPlot.set_edges`（772） | 更新超边曲线、颜色、线型和标签组件。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `WeigthedIncidenceMatrixForQuotientGraph`（943） | 从边轨道选代表并构造赋权关联矩阵；连通代表不存在时可能失败，当前采用更稳健的轨道商算子。 | 已有轨道商算子Quotient_Graph；旧代表超图与当前算子不是相同对象，不伪造等价别名。 |
| `myreprhtml`（1322） | 规范化布局后输出超图HTML预览。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `getPath`（1336） | 沿指定方向追踪超图内部路，原循环缺少歧义与终止保护。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `list2dtopanda`（1355） | 把二维数据转换为带行列名的Pandas样式表。 | 现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。 |
| `get_components`（1366） | 抽取指定内部路及对应的赋权关联子矩阵，并展示表格。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `LinkG`（1943） | 用两条内部路在主超图上接入根超图；单根分支写死了顶点与路长。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `weighted_incidence_graph`（2058） | 画带归一化关联权的点边二部图。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Rotate_Shift`（2139） | 让两组顶点重心连线转到目标方向，并平移指定原点。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Valleys`（2178） | 扫描旋转角度，寻找包围盒面积指标的局部极小值。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Rotate`（2206） | 旋转、缩放并居中超图坐标。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Normalize_Pos`（2224） | 按包围盒指标的极小值选择绘图旋转方向。 | 现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。 |
| `Graph2TeX`（2236） | 生成TeX并调用外部引擎渲染，现有TikZ导出仅覆盖源码部分。 | 现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。 |
| `HyperTree1`（2396） | 拼接四个基本分支与内部路的专门超树族。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `U1`（2573） | 由两个3一致松路与两条内部路构造的专门图族，使用固定顶点编号。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |
| `U2`（2580） | 在三边3一致松路中加内部路的专门图族。 | graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。 |

### LinearAlgebra.sage（9条）

| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |
| --- | --- | --- |
| `bk_rop1`（63） | 交换矩阵的两个块行。 | block_matrix_analysis已提供显式块尺寸的提取、排列和分块乘积贡献；不要求旧Sage分块元数据对象。 |
| `bk_rop2`（72） | 用标量或方阵左乘某一块行。 | block_matrix_analysis已提供显式块尺寸的提取、排列和分块乘积贡献；不要求旧Sage分块元数据对象。 |
| `bk_rop3`（80） | 向某一块行加另一块行的矩阵倍数。 | block_matrix_analysis已提供显式块尺寸的提取、排列和分块乘积贡献；不要求旧Sage分块元数据对象。 |
| `movelines`（114） | 平移二维直线，使它们经过指定位置。 | research_environment检测可选组件及TeX，接入边界见RESEARCH_WORKFLOWS.md；完整隐式绘图和移动直线仍不在本轮实现范围。 |
| `plotequs`（121） | 画二维隐式方程组。 | research_environment检测可选组件及TeX，接入边界见RESEARCH_WORKFLOWS.md；完整隐式绘图和移动直线仍不在本轮实现范围。 |
| `plot3dequs`（128） | 画三维隐式曲面组。 | research_environment检测可选组件及TeX，接入边界见RESEARCH_WORKFLOWS.md；完整隐式绘图和移动直线仍不在本轮实现范围。 |
| `mat_generlize`（256） | 用省略号替换矩阵指定行列，生成概括性排版。 | 现有SymPy基础运算可组合使用；旧演示排版接口尚未等价适配。 |
| `Jordan_block`（359） | 用多项式伴随块与次对角连接构造块，不能直接当成普通Jordan块。 | block_matrix_analysis已提供多项式伴随块对角构造并验证特征多项式乘积；不误用Jordan分解，未复刻旧返回对象。 |
| `Jordan_form`（364） | 按多项式因子列表拼接上述块；原实现只取第一个因子，需核对。 | block_matrix_analysis已提供多项式伴随块对角构造并验证特征多项式乘积；不误用Jordan分解，未复刻旧返回对象。 |

## 本轮已经补齐或复用的定义

以下是Python库适配，不声称完整复刻Sage类型与所有参数；只有工具目录中的名称可供模型直接调用。

| 原定义 | 功能 | 新Python入口 | 适配范围 |
| --- | --- | --- | --- |
| `myCombinatorics.sage:124 getGridPath` | 把0/1步序列画成平面格路径。 | `graph_research.algebra.combinatorics.getGridPath` | 返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。 |
| `myCombinatorics.sage:132 gridPath` | 逐步向右或向上画格路径，可同时返回坐标。 | `graph_research.algebra.combinatorics.gridPath` | 返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。 |
| `myCombinatorics.sage:146 lattice_path` | 由指定向右步的位置集合生成格路径。 | `graph_research.algebra.combinatorics.lattice_path` | 返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。 |
| `myCombinatorics.sage:162 rectangle` | 画矩形边框或填充矩形。 | `graph_research.algebra.combinatorics.rectangle` | 返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。 |
| `myCombinatorics.sage:169 chess_board` | 按回调颜色绘制矩阵棋盘并显示行列标签。 | `graph_research.algebra.combinatorics.chess_board` | 返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。 |
| `myCombinatorics.sage:257 getCycleIndex1` | 将群循环分拆直接作为单项式指数的旧编码；与标准循环指标表示不同。 | `graph_research.algebra.combinatorics.getCycleIndex1` | 保留旧分拆指数编码；不是标准循环指标，不用于Pólya计数。仅Python库入口。 |
| `myCombinatorics.sage:284 getCycleIndex` | 按群元素的循环长度计算标准归一化循环指标多项式。 | `graph_research.algebra.combinatorics.getCycleIndex` | 对完整有限置换群求标准循环指标；已接组合计算工具。 |
| `GraphTheory.sage:25 edge` | 带边序号、权重和标签的顶点元组。 | `graph_research.hypergraphs.model.edge` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:38 edge.issuperset` | 判断边是否包含指定顶点集。 | `graph_research.hypergraphs.model.edge.issuperset` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:41 edge.__sub__` | 边顶点集合差。 | `graph_research.hypergraphs.model.edge.__sub__` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:44 edge.intersection` | 边顶点集合交。 | `graph_research.hypergraphs.model.edge.intersection` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:47 edge.__add__` | 合并两组边顶点。 | `graph_research.hypergraphs.model.edge.__add__` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:62 edge.__and__` | 边顶点集合交。 | `graph_research.hypergraphs.model.edge.__and__` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:65 edge.__getitem__` | 按位置读取边的顶点。 | `graph_research.hypergraphs.model.edge.__getitem__` | 复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。 |
| `GraphTheory.sage:70 Index` | 提取一组边对象的序号。 | `graph_research.graphs.Index` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:564 polynomials_for_addstarsgraph` | 用原矩阵和附叶数量推导加星图的特征多项式。 | `graph_research.graphs.polynomials_for_addstarsgraph` | 无权简单图L/Q的精确Schur表达式；拒绝旧代码不正确的A分支。 |
| `GraphTheory.sage:965 set_edge_weight` | 按边或按同权边组赋权，未指定边可取默认权重。 | `graph_research.graphs.set_edge_weight` | 默认复制或返回数值矩阵；不隐式改动原图。set_edge_weight可显式copy=False；原无权谱工具不会自动读取这些权重。 |
| `GraphTheory.sage:1032 edge2graph` | 用有两个指定端点的图替换原图一条边。 | `graph_research.graphs.edge2graph` | 识别替换端点、隔离内部顶点、保留孤立点；图结构变换工具提供单边替换，Python接口还可批量替换。 |
| `GraphTheory.sage:1049 replace_edges_by_graph` | 批量用指定图替换指定边，识别端点并隔离内部顶点。 | `graph_research.graphs.replace_edges_by_graph` | 识别替换端点、隔离内部顶点、保留孤立点；图结构变换工具提供单边替换，Python接口还可批量替换。 |
| `GraphTheory.sage:1392 PartProduct` | 只在选定顶点子图上作图积，再接回外部邻边。 | `graph_research.graphs.PartProduct` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:1478 checksign1` | 返回多项式非零系数的符号集合。 | `graph_research.graphs.checksign1` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:1624 weight_edges` | 返回加权邻接矩阵并设置权重；原实现引用未定义D。 | `graph_research.graphs.weight_edges` | 默认复制或返回数值矩阵；不隐式改动原图。set_edge_weight可显式copy=False；原无权谱工具不会自动读取这些权重。 |
| `GraphTheory.sage:1646 complex_weight` | 给选定有向边赋i、反向赋−i，依赖原有问题的weight_edges。 | `graph_research.graphs.complex_weight` | 默认复制或返回数值矩阵；不隐式改动原图。set_edge_weight可显式copy=False；原无权谱工具不会自动读取这些权重。 |
| `GraphTheory.sage:1704 pick_vertices` | 按度把顶点分组，可取第k小的度及对应顶点。 | `graph_research.graphs.pick_vertices` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:1763 list2dict` | 按二元记录首项分组收集第二项。 | `graph_research.graphs.list2dict` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:1838 cayley_graph` | 有限半群或群的左/右/双侧Cayley有向图，可保留生成元标签、重边和自环。 | `graph_research.graphs.cayley_graph` | 支持左右/双侧及有限半群；桌面入口使用右侧简单有向图，原值和方向保留。 |
| `GraphTheory.sage:2016 mygraphmul` | 整数参数表示不交并复制，图参数表示迭代笛卡尔积。 | `graph_research.graphs.mygraphmul` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:2047 mygraphsub` | 复制原图并删去另一个图的边。 | `graph_research.graphs.mygraphsub` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:2181 random_symmetric_matrix` | 生成指定整数区间的随机对称矩阵。 | `graph_research.graphs.random_symmetric_matrix` | 返回NumPy整数对称数组，区间两端均包含；可固定局部随机种子。 |
| `GraphTheory.sage:3094 AMdb` | 按相邻端点度倒数之和构造赋权邻接矩阵。 | `graph_research.graphs.AMdb` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `GraphTheory.sage:3147 Cycle` | 根据给定顶点循环顺序构造圈。 | `graph_research.graphs.Cycle` | 使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。 |
| `hypergraph_v2.sage:360 HyperG.add_star` | 附加若干共享同一个根顶点集的超边。 | `graph_research.hypergraphs.Hypergraph.add_star` | 保留原权重和孤立点，新边权为1；共享根集，不是附接链式路径。已接超图变换工具。 |
| `hypergraph_v2.sage:380 HyperG.add_stars` | 按多组根集批量附加超边。 | `graph_research.hypergraphs.Hypergraph.add_stars` | 保留原权重和孤立点，新边权为1；共享根集，不是附接链式路径。已接超图变换工具。 |
| `hypergraph_v2.sage:442 HyperG.eigenVfun` | 生成一致超图Laplacian张量的特征方程向量。 | `graph_research.hypergraphs.Hypergraph.eigenVfun` | 非空一致超图；返回SymPy列向量，生成L张量方程而不求解。已接结构工具。 |
| `hypergraph_v22.sage:416 HyperG.add_star` | 附加若干共享同一个根顶点集的超边。 | `graph_research.hypergraphs.Hypergraph.add_star` | 保留原权重和孤立点，新边权为1；共享根集，不是附接链式路径。已接超图变换工具。 |
| `hypergraph_v22.sage:436 HyperG.add_stars` | 按多组根集批量附加超边。 | `graph_research.hypergraphs.Hypergraph.add_stars` | 保留原权重和孤立点，新边权为1；共享根集，不是附接链式路径。已接超图变换工具。 |
| `hypergraph_v22.sage:498 HyperG.eigenVfun` | 生成一致超图Laplacian张量的特征方程向量。 | `graph_research.hypergraphs.Hypergraph.eigenVfun` | 非空一致超图；返回SymPy列向量，生成L张量方程而不求解。已接结构工具。 |
| `LinearAlgebra.sage:96 show_equtions` | 把方程组排版为大括号LaTeX。 | `graph_research.algebra.linear.show_equtions` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:106 stdequs` | 将线性等式整理为变量项在左、常数项在右。 | `graph_research.algebra.linear.stdequs` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:149 el_rop2` | 某一行数乘，并显示变换过程。 | `graph_research.algebra.linear.el_rop2` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:154 el_rop3` | 向某一行加另一行的倍数，并显示过程。 | `graph_research.algebra.linear.el_rop3` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:164 el_cop2` | 某一列数乘，并显示过程。 | `graph_research.algebra.linear.el_cop2` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:169 el_cop3` | 向某一列加另一列的倍数，并显示过程。 | `graph_research.algebra.linear.el_cop3` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:174 lst2ltx` | 把矩阵和符号列表连接为LaTeX，可用行列式边框。 | `graph_research.algebra.linear.lst2ltx` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:184 sum_hold` | 生成不提前合并的矩阵/行列式求和LaTeX。 | `graph_research.algebra.linear.sum_hold` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:194 split_row` | 拆分矩阵某行，将行列式展开为各拆分矩阵的和。 | `graph_research.algebra.linear.split_row` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:206 split_vector` | 把向量拆成若干只有一个非零分量的向量。 | `graph_research.algebra.linear.split_vector` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:285 do_Actions` | 执行按顺序给出的六类初等行列变换。 | `graph_research.algebra.linear.do_Actions` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:301 Op_links` | 把初等变换编码生成LaTeX箭头说明。 | `graph_research.algebra.linear.Op_links` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:318 do_show_ops` | 生成初等变换前后矩阵与箭头的LaTeX过程。 | `graph_research.algebra.linear.do_show_ops` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:323 Mat2PR` | 把符号矩阵转换为多项式系数域中的矩阵。 | `graph_research.algebra.linear.Mat2PR` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:331 matrix_round` | 仅在误差阈值允许时对矩阵元素舍入/转整数。 | `graph_research.algebra.linear.matrix_round` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |
| `LinearAlgebra.sage:335 map_round` | 对矩阵或序列逐项按误差阈值舍入。 | `graph_research.algebra.linear.map_round` | 返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。 |

## 清单修正

缺失类不能因为None对象本身有__init__/__repr__就标为可用。MyIdentity.__init__、MyIdentity.__repr__及TCBSpline.__init__已恢复待迁移状态；所有可用记录现在逐个验证真实模块路径可调用。

源码提取现在跨过多行字符串中的TeX内容，并保留带字符串默认参数的真实函数；不执行旧Sage源码。原始11个文件未修改。

替换前的完整180条基线保存在[JSON](docs/sage-pending-baseline-v0211.json)，本报告的机器可读结果见[审计JSON](docs/sage-replacement-review.json)。
