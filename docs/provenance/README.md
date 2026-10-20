# 源码迁移与来源记录

此目录保存开发追溯材料，不是运行时工具模块，也不作为当前功能完成率。

- `migration_catalog.json`：按当前分发功能筛选的定义记录，包含原11个文件的名称、SHA256、行数、原函数位置、Python映射、适配范围和历史源码摘录。
- `rights-status.json`：发布授权核对状态；当前为cleared；项目所有者确认公开授权并选择MIT，保留原作者署名和追溯记录。
- 根目录`MIGRATION_STATUS.md`、`SAGE_REMAINING_REVIEW.md`及`docs/sage-replacement-review.json`继续保存迁移统计与功能适配记录。
- `graph_research/data/sage_reference.json`是用于数值回归的已知结果基准，继续保留；它不是旧代码查找或Sage桥接模块。

当前发布目录只保留分发功能的定义与摘录，撤下的两条可选组合函数记录已移除。原始11个源文件的SHA256仍记录在source_files中；该筛选后的JSON不能再按原始完整目录的文件摘要校验。旧函数名称及pending状态只记录历史接口适配，不等于相应科研用途缺失。

运行时已移除`lookup_legacy`、`migration-status`及桌面“旧代码迁移参考”分类。维护者如需重新生成历史记录，可以运行：

```powershell
python tools/build_migration_catalog.py --source "原始Sage文件目录"
python tools/build_sage_review.py
```

此维护过程只解析源码，不运行Sage。普通安装和使用不需要原始文件、Sage或WSL。源码及历史摘录按项目所有者确认的MIT授权发布，署名与原始哈希继续保留，参见根目录LICENSE-STATUS.md。
