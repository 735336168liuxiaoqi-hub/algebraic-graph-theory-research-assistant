# 工作流程 · Mermaid 版本

由workflows.json生成；图像版本与使用说明见[工作流程](../WORKFLOW.md)。

## 代数图论科研助手 · 工作流程

```mermaid
flowchart TB
    offline["本地工具<br/>分类选择函数，无需模型API"]:::manual
    api["API 科研对话<br/>配置兼容模型服务"]:::model
    mcp["MCP 主agent接入<br/>使用主agent的模型"]:::host
    form["填写参数或输入图<br/>表单、JSON、鼠标构图"]:::manual
    plan["自然语言提出需求<br/>模型澄清、选择或组合工具"]:::model
    delegate["委派结构化计算任务<br/>固定步骤、批量或参数扫描"]:::host
    validate["统一参数与图对象<br/>校验工具契约、图类型及数学前提"]:::guard
    execute["受保护的本地执行<br/>预算、完整性、资源限制、取消及执行回执"]:::guard
    evidence["保留结果与执行证据<br/>数值、图对象、坐标、逐步状态与验证信息"]:::data
    present["查看、导出与继续研究<br/>表格、结构图、PNG / SVG / PDF、TikZ / TeX"]:::data
    bundle["成果中心与结果包<br/>保存当前任务 / 对话的记录、数据和附件"]:::data
    offline --> form
    api --> plan
    mcp --> delegate
    form --> validate
    plan --> validate
    delegate --> validate
    validate --> execute
    execute --> evidence
    evidence --> present
    present --> bundle
    classDef process fill:#f5f7fa,stroke:#c6d1da,color:#233845,stroke-width:1.5px
    classDef manual fill:#eaf5f1,stroke:#8dbbb0,color:#175a4a,stroke-width:1.5px
    classDef model fill:#edf2fc,stroke:#a1b8e7,color:#284f91,stroke-width:1.5px
    classDef host fill:#f0edfa,stroke:#b5a7da,color:#5b438c,stroke-width:1.5px
    classDef guard fill:#e9f3f7,stroke:#8fb1c3,color:#224d64,stroke-width:1.5px
    classDef data fill:#f0f6f4,stroke:#adc7bc,color:#2b574a,stroke-width:1.5px
    classDef warning fill:#fcf4e7,stroke:#d7b985,color:#805b26,stroke-width:1.5px
    classDef decision fill:#ffffff,stroke:#9fadb9,color:#344c5c,stroke-width:1.5px
```

## API 科研对话 · 从问题到计算结果

```mermaid
flowchart TB
    ask["提出自然语言问题<br/>可插入明确版本的图对象"]:::manual
    context["读取任务上下文<br/>当前图对象、偏好与已审阅经验"]:::data
    clear{"需求是否明确？"}:::decision
    reply["向用户澄清<br/>等待真实回复"]:::manual
    known{"已有工具能解决？"}:::decision
    extension["进入新工具评估<br/>见扩展工作流程"]:::warning
    plan["选择单工具或生成工具计划<br/>明确参数、图版本和前序结果绑定"]:::model
    review["按需查看并确认计划<br/>或回复修改需求"]:::manual
    run["在本地执行确定步骤<br/>确定步骤之间无需逐步请求模型"]:::guard
    failure["失败、取消或预算用尽<br/>保留已有记录与错误"]:::warning
    interpret["模型读取摘要并解释结果<br/>完整数据保留本地，可按需查询"]:::model
    save["保存回答、计算记录与附件<br/>继续提问、成果导出与回溯"]:::data
    ask --> context
    context --> clear
    clear -->|不明确| reply
    reply -->|补充需求| context
    clear -->|明确| known
    known -->|不能| extension
    known -->|可以| plan
    plan -->|启用计划查看| review
    plan -->|直接执行| run
    review -->|用户确认| run
    run -->|异常/停止| failure
    run -->|取得结果| interpret
    failure -->|保存记录| save
    interpret --> save
    classDef process fill:#f5f7fa,stroke:#c6d1da,color:#233845,stroke-width:1.5px
    classDef manual fill:#eaf5f1,stroke:#8dbbb0,color:#175a4a,stroke-width:1.5px
    classDef model fill:#edf2fc,stroke:#a1b8e7,color:#284f91,stroke-width:1.5px
    classDef host fill:#f0edfa,stroke:#b5a7da,color:#5b438c,stroke-width:1.5px
    classDef guard fill:#e9f3f7,stroke:#8fb1c3,color:#224d64,stroke-width:1.5px
    classDef data fill:#f0f6f4,stroke:#adc7bc,color:#2b574a,stroke-width:1.5px
    classDef warning fill:#fcf4e7,stroke:#d7b985,color:#805b26,stroke-width:1.5px
    classDef decision fill:#ffffff,stroke:#9fadb9,color:#344c5c,stroke-width:1.5px
```

## MCP 委派 · 主agent如何调用科研助手

```mermaid
flowchart TB
    host["主agent理解用户任务<br/>自然语言规划使用主agent自己的模型"]:::host
    catalog["research_catalog<br/>发现工具、读取契约与版本指纹"]:::host
    submit["research_submit<br/>提交固定步骤 / 扫描 / 批量任务"]:::host
    replay["相同编号与相同输入<br/>返回原任务，不新增计算"]:::data
    run["后台受保护计算<br/>快速返回task_id，保存预算与逐步记录"]:::guard
    cancel["research_cancel<br/>请求停止，保留已有记录"]:::warning
    get["research_get<br/>按原task_id查询，不重复创建任务"]:::host
    state{"当前任务状态？"}:::decision
    running["仍在运行<br/>短暂等待后再查询"]:::data
    interaction["等待用户回复或审批<br/>主agent完整转交interaction"]:::manual
    user["可信用户入口<br/>用户操作后签发event_id"]:::manual
    resume["research_resume<br/>只转交已签发的event_id"]:::host
    settled["完成、失败或已取消<br/>保留实际结果和未完成部分"]:::data
    inspect["按需读取结果与已登记附件<br/>research_inspect_result<br/>research_read_artifact"]:::host
    deliver["主agent整理并交付给用户<br/>数据、图形、TeX或结果包"]:::host
    host --> catalog
    catalog --> submit
    submit -->|已有任务| replay
    submit -->|新任务| run
    replay --> get
    run -->|用户停止| cancel
    cancel --> settled
    run --> get
    get --> state
    state -->|运行中| running
    running --> get
    state -->|需用户操作| interaction
    interaction --> user
    user --> resume
    resume -->|核验事件后继续| run
    state -->|已停止/结束| settled
    settled --> inspect
    inspect --> deliver
    classDef process fill:#f5f7fa,stroke:#c6d1da,color:#233845,stroke-width:1.5px
    classDef manual fill:#eaf5f1,stroke:#8dbbb0,color:#175a4a,stroke-width:1.5px
    classDef model fill:#edf2fc,stroke:#a1b8e7,color:#284f91,stroke-width:1.5px
    classDef host fill:#f0edfa,stroke:#b5a7da,color:#5b438c,stroke-width:1.5px
    classDef guard fill:#e9f3f7,stroke:#8fb1c3,color:#224d64,stroke-width:1.5px
    classDef data fill:#f0f6f4,stroke:#adc7bc,color:#2b574a,stroke-width:1.5px
    classDef warning fill:#fcf4e7,stroke:#d7b985,color:#805b26,stroke-width:1.5px
    classDef decision fill:#ffffff,stroke:#9fadb9,color:#344c5c,stroke-width:1.5px
```

## 新工具引入 · 先复用，再评估与审批

```mermaid
flowchart TB
    need["提出尚未满足的科研需求<br/>说明数学目标与期望输出"]:::manual
    defined{"定义、规模与样例齐全？"}:::decision
    clarify["先向用户澄清<br/>补齐输入输出和验收依据"]:::manual
    reuse{"可复用或组合已有工具？"}:::decision
    existing["直接调用已有工具<br/>不创建新的工具包"]:::data
    bounded{"适合受限扩展机制？"}:::decision
    manual["形成独立开发说明<br/>需要新依赖或超出限制<br/>转人工开发与独立评估"]:::warning
    assess["评估新增范围与大致消耗<br/>数学定义、适用范围、验收、估算与限制"]:::data
    approve{"用户批准本次范围？"}:::decision
    reject["拒绝或修改需求<br/>未获批准不生成并安装"]:::manual
    generate["模型实现独立工具包<br/>按批准范围生成，不修改基础包"]:::model
    test["受保护验证与范围核验<br/>样例、预算与完整性；失败证据保留"]:::guard
    pass{"验证通过？"}:::decision
    fail["验证失败或中断<br/>未安装；保留失败证据"]:::warning
    installed["登记独立扩展工具<br/>可发现、可复用、版本可追溯"]:::data
    need --> defined
    defined -->|不齐全| clarify
    clarify -->|补充需求| need
    defined -->|齐全| reuse
    reuse -->|可以| existing
    reuse -->|不能| bounded
    bounded -->|不适合| manual
    bounded -->|适合| assess
    assess --> approve
    approve -->|拒绝/修改| reject
    approve -->|批准| generate
    generate --> test
    test --> pass
    pass -->|未通过| fail
    pass -->|通过| installed
    classDef process fill:#f5f7fa,stroke:#c6d1da,color:#233845,stroke-width:1.5px
    classDef manual fill:#eaf5f1,stroke:#8dbbb0,color:#175a4a,stroke-width:1.5px
    classDef model fill:#edf2fc,stroke:#a1b8e7,color:#284f91,stroke-width:1.5px
    classDef host fill:#f0edfa,stroke:#b5a7da,color:#5b438c,stroke-width:1.5px
    classDef guard fill:#e9f3f7,stroke:#8fb1c3,color:#224d64,stroke-width:1.5px
    classDef data fill:#f0f6f4,stroke:#adc7bc,color:#2b574a,stroke-width:1.5px
    classDef warning fill:#fcf4e7,stroke:#d7b985,color:#805b26,stroke-width:1.5px
    classDef decision fill:#ffffff,stroke:#9fadb9,color:#344c5c,stroke-width:1.5px
```

## Algebraic Graph Theory Research Assistant

```mermaid
flowchart TB
    offline["Local tools<br/>Choose a tool; no model API"]:::manual
    api["API research chat<br/>Connect a model service"]:::model
    mcp["MCP host integration<br/>Use the host agent's model"]:::host
    form["Enter parameters or a graph<br/>Forms, JSON or visual editing"]:::manual
    plan["Describe a research task<br/>Clarify, select or compose tools"]:::model
    delegate["Delegate a structured task<br/>Steps, batches or alpha scans"]:::host
    validate["Shared parameters and graph objects<br/>Validate contracts, graph types and mathematical assumptions"]:::guard
    execute["Protected local execution<br/>Budgets, core integrity, resource limits, cancellation and receipts"]:::guard
    evidence["Results with execution evidence<br/>Values, graph objects, coordinates, step status and verification"]:::data
    present["Inspect, export and continue research<br/>Tables, graph drawings, PNG / SVG / PDF and TikZ / TeX"]:::data
    bundle["Result center and bundles<br/>Preserve records, data and artifacts for the task or conversation"]:::data
    offline --> form
    api --> plan
    mcp --> delegate
    form --> validate
    plan --> validate
    delegate --> validate
    validate --> execute
    execute --> evidence
    evidence --> present
    present --> bundle
    classDef process fill:#f5f7fa,stroke:#c6d1da,color:#233845,stroke-width:1.5px
    classDef manual fill:#eaf5f1,stroke:#8dbbb0,color:#175a4a,stroke-width:1.5px
    classDef model fill:#edf2fc,stroke:#a1b8e7,color:#284f91,stroke-width:1.5px
    classDef host fill:#f0edfa,stroke:#b5a7da,color:#5b438c,stroke-width:1.5px
    classDef guard fill:#e9f3f7,stroke:#8fb1c3,color:#224d64,stroke-width:1.5px
    classDef data fill:#f0f6f4,stroke:#adc7bc,color:#2b574a,stroke-width:1.5px
    classDef warning fill:#fcf4e7,stroke:#d7b985,color:#805b26,stroke-width:1.5px
    classDef decision fill:#ffffff,stroke:#9fadb9,color:#344c5c,stroke-width:1.5px
```
