# Sage包迁移清单

逐函数记录见docs/provenance/migration_catalog.json。

本表仅用于旧源码追溯，不作为功能完成率或开发待办。pending表示旧定义尚未逐项适配，不等于科研功能缺失；能力验收见FUNCTIONAL_COVERAGE.md。原生实现也不声称所有参数均与Sage等价。

| 原文件 | 原生实现可用 | 待迁移 | 重复定义 |
| --- | ---: | ---: | ---: |
| myCombinatorics.sage | 19 | 13 | 0 |
| MyPolynomial.sage | 5 | 0 | 0 |
| MyTools.sage | 12 | 2 | 0 |
| MyUtility.sage | 3 | 22 | 0 |
| Tensor.sage | 48 | 1 | 0 |
| GraphTheory.sage | 134 | 31 | 0 |
| GraphTheory1.sage | 0 | 0 | 165 |
| hypergraph_v2.sage | 112 | 25 | 0 |
| hypergraph_v22.sage | 122 | 27 | 0 |
| HyperMatrix.sage | 27 | 0 | 0 |
| LinearAlgebra.sage | 32 | 9 | 0 |

## 尚未迁移的定义

- myCombinatorics.sage:65 `my_print`
- myCombinatorics.sage:68 `MyIdentity`
- myCombinatorics.sage:69 `MyIdentity.__init__`
- myCombinatorics.sage:76 `MyIdentity.__repr__`
- myCombinatorics.sage:78 `MyIdentity.__mul__`
- myCombinatorics.sage:84 `MyIdentity.action`
- myCombinatorics.sage:94 `MyIdentity.subs`
- myCombinatorics.sage:103 `MyIdentity.factor`
- myCombinatorics.sage:106 `MyIdentity.simplify`
- myCombinatorics.sage:110 `MyIdentity.show1`
- myCombinatorics.sage:112 `MyIdentity.actionlist`
- myCombinatorics.sage:118 `MyIdentity.show`
- myCombinatorics.sage:225 `MyPowerSeries`
- MyTools.sage:140 `l2math`
- MyTools.sage:151 `L2Math`
- MyUtility.sage:9 `Latex2Image`
- MyUtility.sage:17 `Graph2Image`
- MyUtility.sage:41 `my_repr_html`
- MyUtility.sage:83 `Reshape`
- MyUtility.sage:153 `Table`
- MyUtility.sage:170 `viewgraph`
- MyUtility.sage:188 `htmlview`
- MyUtility.sage:206 `showGA`
- MyUtility.sage:211 `latex_draw`
- MyUtility.sage:232 `Graphics2Data`
- MyUtility.sage:282 `graph_to_html`
- MyUtility.sage:305 `graphs_list_save`
- MyUtility.sage:413 `variable_name`
- MyUtility.sage:427 `TCBSpline`
- MyUtility.sage:428 `TCBSpline.__init__`
- MyUtility.sage:436 `TCBSpline._calc_tangents_kochanek_bartel`
- MyUtility.sage:464 `TCBSpline._calc_tangents_catmull_rom`
- MyUtility.sage:484 `TCBSpline.interpolate`
- MyUtility.sage:561 `graphs_list_show`
- MyUtility.sage:572 `base64ToPng`
- MyUtility.sage:581 `html_add`
- MyUtility.sage:588 `table_add`
- Tensor.sage:294 `Tensor.__call__`
- GraphTheory.sage:401 `plot_by_eigenvector`
- GraphTheory.sage:611 `De_subdivide_claw`
- GraphTheory.sage:634 `De_subdivide_edge`
- GraphTheory.sage:709 `energy_polynomial`
- GraphTheory.sage:1470 `perm_block`
- GraphTheory.sage:1671 `slip_graph`
- GraphTheory.sage:2168 `subdivide`
- GraphTheory.sage:2186 `subdivide1`
- GraphTheory.sage:2244 `add_blossom`
- GraphTheory.sage:2269 `gline_graph_forbidden_subgraphs`
- GraphTheory.sage:2278 `is_gline_graph`
- GraphTheory.sage:2404 `layout_Tree`
- GraphTheory.sage:2511 `ShiftPos`
- GraphTheory.sage:2524 `Pos`
- GraphTheory.sage:2543 `VerticesLabel`
- GraphTheory.sage:2553 `Init`
- GraphTheory.sage:2563 `local_spring`
- GraphTheory.sage:2604 `Rotate_Shift`
- GraphTheory.sage:2812 `GraphPlot`
- GraphTheory.sage:2869 `Plot`
- GraphTheory.sage:2905 `plot_graph_with_labels`
- GraphTheory.sage:2947 `Set_Label_with_Eigenvector`
- GraphTheory.sage:3005 `plotbycycle`
- GraphTheory.sage:3016 `Latex`
- GraphTheory.sage:3054 `Graph2TeX`
- GraphTheory.sage:3206 `Merge_And_Append_Edge`
- GraphTheory.sage:3480 `GraphList2TeX`
- GraphTheory.sage:3574 `GL2TeX`
- GraphTheory.sage:3654 `align_HV`
- GraphTheory.sage:3676 `CenterPos`
- GraphTheory.sage:3697 `rich_repr`
- hypergraph_v2.sage:257 `HyperG.edge_coloring`
- hypergraph_v2.sage:260 `HyperG._spring_layout`
- hypergraph_v2.sage:265 `HyperG.Pos`
- hypergraph_v2.sage:283 `HyperG.setLposDeg1`
- hypergraph_v2.sage:313 `HyperG.setLabPos`
- hypergraph_v2.sage:556 `HyperG._rich_repr_`
- hypergraph_v2.sage:591 `HyperG.Latex`
- hypergraph_v2.sage:653 `HyperG._latex_`
- hypergraph_v2.sage:675 `HyperGraphPlot._repr_`
- hypergraph_v2.sage:686 `HyperGraphPlot.set_vertices`
- hypergraph_v2.sage:715 `HyperGraphPlot.set_edges`
- hypergraph_v2.sage:1083 `myreprhtml`
- hypergraph_v2.sage:1097 `getPath`
- hypergraph_v2.sage:1116 `list2dtopanda`
- hypergraph_v2.sage:1127 `get_components`
- hypergraph_v2.sage:1578 `LinkG`
- hypergraph_v2.sage:1670 `weighted_incidence_graph`
- hypergraph_v2.sage:1736 `Rotate_Shift`
- hypergraph_v2.sage:1762 `Valleys`
- hypergraph_v2.sage:1790 `Rotate`
- hypergraph_v2.sage:1808 `Normalize_Pos`
- hypergraph_v2.sage:1820 `Graph2TeX`
- hypergraph_v2.sage:1944 `HyperTree1`
- hypergraph_v2.sage:2067 `U1`
- hypergraph_v2.sage:2074 `U2`
- hypergraph_v22.sage:287 `HyperG.edge_coloring`
- hypergraph_v22.sage:292 `HyperG._spring_layout`
- hypergraph_v22.sage:297 `HyperG.Pos`
- hypergraph_v22.sage:319 `HyperG.setLposDeg1`
- hypergraph_v22.sage:341 `HyperG.setLposDeg1`
- hypergraph_v22.sage:350 `HyperG.setLabPos`
- hypergraph_v22.sage:612 `HyperG._rich_repr_`
- hypergraph_v22.sage:647 `HyperG.Latex`
- hypergraph_v22.sage:710 `HyperG._latex_`
- hypergraph_v22.sage:732 `HyperGraphPlot._repr_`
- hypergraph_v22.sage:743 `HyperGraphPlot.set_vertices`
- hypergraph_v22.sage:772 `HyperGraphPlot.set_edges`
- hypergraph_v22.sage:943 `WeigthedIncidenceMatrixForQuotientGraph`
- hypergraph_v22.sage:1322 `myreprhtml`
- hypergraph_v22.sage:1336 `getPath`
- hypergraph_v22.sage:1355 `list2dtopanda`
- hypergraph_v22.sage:1366 `get_components`
- hypergraph_v22.sage:1943 `LinkG`
- hypergraph_v22.sage:2058 `weighted_incidence_graph`
- hypergraph_v22.sage:2139 `Rotate_Shift`
- hypergraph_v22.sage:2178 `Valleys`
- hypergraph_v22.sage:2206 `Rotate`
- hypergraph_v22.sage:2224 `Normalize_Pos`
- hypergraph_v22.sage:2236 `Graph2TeX`
- hypergraph_v22.sage:2396 `HyperTree1`
- hypergraph_v22.sage:2573 `U1`
- hypergraph_v22.sage:2580 `U2`
- LinearAlgebra.sage:63 `bk_rop1`
- LinearAlgebra.sage:72 `bk_rop2`
- LinearAlgebra.sage:80 `bk_rop3`
- LinearAlgebra.sage:114 `movelines`
- LinearAlgebra.sage:121 `plotequs`
- LinearAlgebra.sage:128 `plot3dequs`
- LinearAlgebra.sage:256 `mat_generlize`
- LinearAlgebra.sage:359 `Jordan_block`
- LinearAlgebra.sage:364 `Jordan_form`
