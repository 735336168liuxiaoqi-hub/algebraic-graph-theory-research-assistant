# CEM算法参考与实现差异

核对日期：2026-10-24。

算法参考：[dragance106/cema-for-graphs](https://github.com/dragance106/cema-for-graphs)，本地参考文件cema_train_simple_graph.py的SHA256：`4102167ee264a67835b07f80c252ebc3737a937db015dfce74d9027e39ea5d3f`。

已检查本地Python训练层及仓库首页。未发现明确LICENSE文件；本项目未复制或打包该训练器、运行器、JAR或源文件。新实现使用通用的自回归策略采样、精英交叉熵训练及探索机制，保留这一算法来源说明；本段不为上游代码授予许可。

| 方面 | 本项目的独立实现 |
| --- | --- |
| 构造 | 普通图逐边；一般超图采用稀疏边槽／顶点选择，允许环；只有必需的超树条件才用合法生长 |
| 特征 | 部分度、当前边顶点集合和位置等O(n)特征，不复制上游完整观察数组 |
| 训练 | 小型CPU神经网络、64步微批交叉熵、固定学习率及带动量更新；不宣称与上游训练轨迹相同 |
| 状态 | 安全JSON内的float32字节编码、网络及动量、RNG、精英、奖励版本和动作序列；不使用pickle |
| 数学 | Python图／超图评价及独立有理数谱界；训练引导与科研原始目标分开 |
| 环境 | torch为可选search依赖，普通功能不依赖torch；无Java/JVM/JPype/JAR/Sage/WSL/CUDA要求 |
| 运行 | 宿主预算及范围审批、Windows保护进程、分段恢复、回执校验和结构化结果包 |

本地a5借鉴原训练器按代数／批量持续训练的方式，增加worker_rounds多代共用保护进程和同一策略对象；仍独立实现动作重放、微批学习和安全JSON检查点，不复制原程序的完整观察历史数组。完整每代证据流式保存，暂停／结束分析覆盖全部已核验候选；资源档位和上限由用户及宿主授权，而非取消进程保护。

验证只说明列出的环境与样例通过，并不承诺强化学习优于枚举、随机或局部方法。对比应保持候选评价数与时间预算一致，报告独立种子、可行率、原始目标、消耗和结构多样性。

English: the upstream project is an algorithmic reference, not redistributed source. The new implementation uses independent sparse representations, microbatch CPU learning, explicit safe checkpoints and Python-only rewards. No upstream Java bridge, trainer, source file or binary is bundled. Same-budget multi-seed comparisons are required; CEM is not presumed superior.
