# 多场景 VLA 数据处理 Agent 架构设计

日期：2026-06-05

## 背景

当前系统已经实现了导航跟随场景的 VLA 数据处理流程。这个流程目前由单个
ReAct 会话智能体驱动：系统 prompt 中描述导航数据处理的默认链路，ReAct 按
链路调用已注册的 VLA 工具，执行层运行具体工具函数，工具返回结构化结果，
ReAct 再根据结果继续推进、询问用户或总结处理结果。

这个模式适合当前导航数据处理原型，但不是最终目标。长期目标是构建一个多场
景 VLA 数据处理系统。根据当前讨论和流程图，系统未来至少需要覆盖：

- 导航跟随 VLA 数据处理；
- 机械臂 VLA 数据处理；
- 半自动化标注；
- 人工可视化精标；
- 多层级自动化质检；
- 标准化 VLA 数据集入库；
- 数据管理、权限、溯源和统计分析；
- 稀缺样本智能补采建议；
- 自动训练调度；
- 数据集自动切分；
- VLA 模型分布式训练；
- 最优模型权重自动归档；
- 自动化模型评测；
- 标准化测试报告生成；
- 指标达标后的模型上线部署；
- 指标不达标后的调参回流重训；
- 线上机器人运行产生新真实数据，并反馈到多场景数据采集。

当前只有导航数据处理代码，机械臂处理代码还没有。因此架构设计必须做到：
**实现时先接入导航数据处理，但整体架构从一开始就是多场景的，未来只需要注
册机械臂相关工具、补充机械臂场景模板和数据画像逻辑，就可以接入机械臂处理
流程。**

## 当前问题

现在的 VLA 导航处理流程本质上是：

```text
用户请求
  -> 单个 ReAct 根据 prompt 中的导航默认流程调用工具
  -> 工具执行具体脚本
  -> 返回结构化结果
  -> ReAct 汇报进展或总结
```

这个模式存在几个限制。

第一，处理场景会变化。用户将来可能让智能体处理导航跟随数据，也可能让智能
体处理机械臂数据。不同场景的数据结构、处理步骤、标注方式、质检方式和输出
格式都可能不同。

第二，同一场景下的数据形态也会变化。以当前导航数据为例，有的数据不包含
gridmap，因此最后转移最终文件时不应该要求转移 gridmap；有的数据 topic 名称
可能变化，这时就需要使用支持不同或自定义 topic 的处理代码或工具变体。

第三，相同步骤也可能对应不同工具。比如同样是“同步/拆分”步骤，默认 topic
数据可以使用默认工具，自定义 topic 数据则应使用另一个支持 topic 配置的工具。

第四，完整系统不是一条直线。流程图中包含质检不合格后的回流重处理/重采集、
标准化入库后的统计分析、训练评测后的调参重训、线上机器人产生新数据后的再
采集闭环。这些都更适合由状态机显式管理，而不是藏在一个巨大 prompt 里。

因此，系统需要从“单 ReAct 按固定 prompt 调工具”升级为：

```text
场景识别
  -> 数据画像
  -> 受约束的计划生成
  -> 计划校验和确认
  -> 按计划执行
  -> 质检和回流
```

## 目标

本架构设计的目标是：

1. 支持多场景 VLA 数据处理，先实现导航场景，给机械臂场景保留清晰入口。
2. 引入 Plan-Agent，由它根据用户目标、场景模板、工具能力目录和数据画像生成
   结构化处理计划。
3. 约束 Plan-Agent，避免其凭空规划。Plan-Agent 必须在“场景模板 + 工具能力目
   录 + 数据画像”的约束下规划。
4. 引入 Executor-Agent，由它根据 Plan-Agent 生成并通过校验的计划逐步执行。
5. 使用 LangGraph 作为外层编排层，负责状态流转、用户确认、断点、重试、人工
   checkpoint、质检分支和最终总结。
6. 保留现有 ToolSpec/runtime 执行层，所有真实工具执行仍然通过注册工具进入执
   行层，不让 Agent 直接跑脚本。
7. 所有工具继续返回结构化结果，便于 Executor-Agent 判断下一步，也便于日志、
   断点恢复和失败诊断。

## 非目标

第一阶段不做以下事情：

- 不实现机械臂具体处理工具；
- 不替换现有导航 VLA 工具；
- 不让 Plan-Agent 直接执行长耗时、写文件或高风险处理步骤；
- 不让 Executor-Agent 在执行过程中随意重写主流程；
- 不一次性实现完整训练、评测、部署平台。

这些能力应在架构中预留入口，但初始实现应聚焦于多场景架构骨架和导航场景的
完整接入，并且初始实现应该能够完整展示智能体处理导航场景的数据处理流程。

## 总体方案

推荐采用方案：

```text
LangGraph 外层编排
  + Plan-Agent 生成计划
  + Executor-Agent 执行计划
  + ToolSpec/runtime 执行工具
```

核心分工如下：

```text
LangGraph
  负责全局状态和节点路由。

Plan-Agent
  负责决定“应该怎么处理”，生成结构化 VLAWorkflowPlan。

Executor-Agent
  负责决定“当前这一步执行完后怎么推进”，但不重新设计主流程。

Tool Runtime
  负责真正执行工具函数，并返回结构化结果。
```

一句话概括：

```text
Plan-Agent 决定计划；
Executor-Agent 执行计划；
LangGraph 决定系统流向；
工具层完成真实处理。
```

## 高层数据流

```text
1. 用户提出需求。
2. LangGraph 初始化工作流状态。
3. Plan-Agent 根据用户请求识别处理场景。
4. 如果缺少必要信息，Plan-Agent 通过 LangGraph 向用户追问。
5. Plan-Agent 调用只读/探测/dry-run 工具检查数据形态。
6. Plan-Agent 创建结构化数据画像。
7. Plan-Agent 选择场景模板。
8. Plan-Agent 结合用户目标、场景模板、数据画像和工具能力目录生成 VLAWorkflowPlan。
9. LangGraph 使用确定性节点校验计划。
10. 系统向用户展示计划摘要，并等待确认。
11. Executor-Agent 按计划逐 stage 调用工具。
12. Tool Runtime 执行具体工具函数，返回结构化结果。
13. Executor-Agent 解读结果，判断继续、重试、暂停、询问用户或停止。
14. LangGraph 更新状态，并路由到下一 stage、人工 checkpoint、质检、回流或总结。
15. 质检结果决定数据标准化入库、重处理或回流重采集。
```

## LangGraph 节点设计

LangGraph 是外层状态机。不是所有节点都应该是 Agent。有些节点必须是普通程
序节点，因为它们属于安全边界、状态更新或确定性路由。

推荐主图如下：

```text
user_request
  -> plan_agent_subgraph
  -> validate_plan
  -> ask_confirmation
  -> select_next_stage
  -> executor_agent
  -> update_state
  -> route_after_stage
  -> select_next_stage
  -> ...
  -> quality_gate
  -> final_summary
```

### Plan-Agent 子图

以下节点属于 Plan-Agent 的任务范围：

```text
scene_detect
collect_required_info
inspect_data
build_data_profile
select_scene_template
generate_workflow_plan
```

`scene_detect` 负责根据用户请求判断处理场景，例如导航 VLA、机械臂 VLA、质检、
入库、训练、评测或其他任务。

`collect_required_info` 负责判断用户是否提供了足够信息，例如日期、raw root、
clip root、处理目标、是否全量处理、是否允许执行长耗时步骤等。如果缺少信息，
LangGraph 应跳转到用户追问节点，然后回到 Plan-Agent 子图继续规划。

`inspect_data` 负责让 Plan-Agent 调用只读或 dry-run 工具检查真实数据形态。对
导航场景来说，这包括目录结构、db3/ROS 信息、topic 列表、clip 片段、是否存在
gridmap、是否存在同步数据、是否已有标注文件、可用脚本版本等。

`build_data_profile` 负责把 inspection 工具结果整理为结构化数据画像。

`select_scene_template` 负责选择场景模板。第一阶段实现 `navigation_vla`，同时
保留 `manipulation_vla` 模板入口，但标记为未实现。

`generate_workflow_plan` 负责生成最终的 `VLAWorkflowPlan`。

### 普通 LangGraph 节点

以下节点不应该交给 Agent 自由发挥，而应作为普通程序节点实现：

```text
validate_plan
ask_confirmation
save_plan
load_plan
select_next_stage
update_state
route_after_stage
```

`validate_plan` 检查计划是否合法，包括工具是否存在、参数是否完整、stage 依赖
是否闭合、是否声明人工 checkpoint、是否包含需要确认的写入/执行步骤、是否使
用了当前场景允许的工具。

`ask_confirmation` 在执行任何长耗时、写文件、执行脚本或高风险步骤前，向用户
展示计划摘要并等待确认。

`select_next_stage` 从 plan 状态中确定下一个待执行 stage。这个逻辑应是确定性
的，不应该让 Executor-Agent 自己猜。

`update_state` 把当前 stage 的执行结果写回 LangGraph 全局状态，记录成功、失
败、跳过、等待人工、产物路径、错误类型、错误信息、next_actions、日志路径和
checkpoint 信息。

`route_after_stage` 根据最新状态决定继续下一步、重试、暂停、询问用户、进入
质检或停止。

### Executor-Agent 节点

Executor-Agent 负责局部执行推理：

```text
execute_stage
interpret_tool_result
decide_next_action
stage_summary
```

`execute_stage` 按当前 plan stage 调用指定工具。

`interpret_tool_result` 解读工具返回的结构化结果，例如 `ok`、`error_type`、
`message`、`artifacts`、`checks`、`next_actions`。

`decide_next_action` 判断下一步是继续、重试、等待人工、跳过可选 stage、请求重
规划，还是停止并总结失败。

`stage_summary` 在合适时机向用户汇报当前 stage 的处理进展、产物路径和下一步。

Executor-Agent 不应该重新设计主流程。如果执行过程中发现 plan 已经不适用，它
应该通过 LangGraph 请求重新进入 Plan-Agent，而不是偷偷改计划。

## Plan-Agent 约束

Plan-Agent 必须在以下四类信息约束下生成计划：

```text
用户目标
场景模板
数据画像
工具能力目录
```

推荐的 Plan-Agent 工作顺序是：

```text
1. 理解用户请求。
2. 识别数据处理场景。
3. 判断是否缺少必要信息。
4. 如缺信息，向用户追问。
5. 调用只读/探测/dry-run 工具检查数据形态。
6. 创建结构化数据画像。
7. 选择场景模板。
8. 根据数据画像对模板做受控调整。
9. 根据工具能力目录选择工具或工具变体。
10. 生成结构化 VLAWorkflowPlan。
```

Plan-Agent 只能使用安全工具：

```text
只读 inspection 工具
list/discovery 工具
validate 工具
dry-run 工具
plan save/load 工具
```

Plan-Agent 不应该直接运行真实处理步骤。

## Executor-Agent 约束

Executor-Agent 的输入应包括：

```text
VLAWorkflowPlan
当前 stage
前面 stage 的结构化结果
运行上下文
```

Executor-Agent 可以做局部恢复判断，但不能自由改写主流程。它可以：

- 执行当前 stage 的工具；
- 解读工具返回结果；
- 在策略允许范围内重试可恢复 stage；
- 在声明的人工 checkpoint 暂停；
- 请求 LangGraph 重新进入 Plan-Agent；
- 总结当前进度和结果。

Executor-Agent 不应该：

- 改变处理场景；
- 插入未声明的高风险 stage；
- 未经允许跳过 required stage；
- 调用当前 plan 未批准的工具。

## VLAWorkflowPlan 模型

系统应新增 `VLAWorkflowPlan`，不要强行复用普通 Data-Juicer operator recipe。
原因是 VLA 工作流包含脚本执行、人工 checkpoint、质检、入库和回流，不只是算
子流水线。

建议结构如下：

```yaml
plan_id: vla_plan_20260605_001
version: 1
intent: "处理 20270515 的导航 VLA 数据"
scenario: navigation_vla
status: pending

inputs:
  raw_root: "/data/raw"
  date: "20270515"
  selected_segments: ["seg_a", "seg_b"]
  scene_mode: "out"

data_profile:
  source_type: ros2_db3
  has_gridmap: false
  topic_schema: default
  topics: []
  missing_required_inputs: []
  recommended_variants:
    extract_and_sync: vla_extract_and_sync
    projection_trajectory: vla_run_projection_and_trajectory

stages:
  - id: inspect_raw_date
    name: "检查导航原始数据"
    tool: vla_inspect_raw_date
    args:
      date: "20270515"
    required: true
    effects: read
    status: pending

  - id: projection_trajectory
    name: "执行点投影与轨迹生成"
    tool: vla_run_projection_and_trajectory
    args:
      use_gridmap: false
    required: true
    effects: execute
    status: pending

checkpoints:
  - id: manual_annotation
    stage_id: run_manual_box_annotation
    type: human_in_loop
    description: "等待用户完成可视化人工标注后再继续。"

quality_gates:
  - id: validate_outputs
    tool: vla_validate_outputs
    required: true

confirmation:
  required_before_execute: true
  reason: "计划包含长耗时和写文件步骤。"

runtime:
  working_dir: "./.djx"
  log_dir: "./.djx/vla_runs/20270515/vla_plan_20260605_001"

history: []
```

## 场景模板

场景模板用于防止 Plan-Agent 凭空规划。模板定义某个场景下的常见步骤、必要输
入、允许工具、变体规则、人工 checkpoint 和质检要求。

### 导航 VLA 模板

第一阶段应实现 `navigation_vla` 模板。

默认步骤：

```text
vla_inspect_raw_date
vla_check_runtime
vla_prepare_raw_temp
vla_extract_and_sync
vla_list_clip_segments
vla_prepare_finish_dataset
vla_build_noobscenes_inputs
vla_run_manual_box_annotation
vla_run_tracking
vla_run_projection_and_trajectory
vla_validate_outputs
```

已知导航变体：

```text
如果数据包含 gridmap 或用户要求处理 gridmap：
  projection/trajectory stage 设置 use_gridmap=true。

如果数据不包含 gridmap：
  设置 use_gridmap=false，最终输出校验也不要求 gridmap。

如果 topic 名称符合默认 schema：
  使用默认 extract/sync 工具。

如果 topic 名称是自定义 schema：
  选择支持自定义 topic 的 extract/sync 工具变体。

如果人工标注后没有 YAML 输出：
  暂停并询问用户是重试、跳过部分 clip，还是终止流程。
```

### 机械臂 VLA 模板

第一阶段只保留 `manipulation_vla` 入口，不实现具体工具。

预留默认步骤：

```text
inspect_manipulation_raw_data
check_manipulation_runtime
split_and_sync
clean
semi_auto_annotation
manual_visual_annotation
validate_outputs
standardize_dataset
```

在机械臂工具实现前，如果用户请求机械臂数据处理，Plan-Agent 应返回明确说明：
当前架构已预留机械臂场景，但具体机械臂处理工具尚未注册，无法执行完整流程。

## 工具能力目录

工具能力目录应从现有 `ToolSpec` registry 自动生成，并补充 VLA 场景相关元信
息。

每个工具应暴露：

```text
工具名
工具描述
输入 schema
输出 schema
tags
effects
confirmation 策略
支持的场景
支持的数据画像条件
是否支持 dry_run
预期产物
可恢复错误类型
```

Plan-Agent 选择工具时必须参考该目录。例如数据画像显示 `topic_schema=custom`
时，Plan-Agent 只能选择声明支持自定义 topic 的工具。

## 数据画像

数据画像是原始数据和计划生成之间的桥梁。Plan-Agent 必须先检查数据并创建数
据画像，再生成 plan。

导航数据画像建议包含：

```text
候选场景
raw root
date
可用原始数据目录
选中的 segments
ROS/db3 元信息
topic 列表
topic schema 分类
必要 topic 是否存在
是否包含 gridmap
是否包含 odom
是否包含 image
是否包含 pointcloud
是否已有 sync_data
是否已有 annotation 文件
推荐工具变体
阻塞问题
警告信息
```

机械臂数据画像字段以后可以独立扩展，不影响外层架构。

## 质检和回流

质检应作为显式 graph 分支，而不是隐藏在某个 Agent 的自然语言推理里。

数据处理阶段：

```text
质检合格
  -> 标准化 VLA 数据集入库
  -> 数据管理和统计分析
  -> 稀缺样本智能补采建议

质检不合格
  -> 生成数据回流重处理计划
  -> 或生成重采集建议
```

训练评测阶段未来可以扩展为：

```text
标准化数据集
  -> 自动训练调度
  -> 数据集自动切分
  -> VLA 模型分布式训练
  -> 最优模型权重自动归档
  -> 全自动模型评测
  -> 自动生成标准化测试报告
  -> 指标达标则模型上线部署
  -> 指标不达标则调参回流重训
  -> 线上机器人运行产生新真实数据
  -> 反馈到多场景数据采集
```

## 初始实现范围

第一阶段建议实现：

1. 新增基于 LangGraph 的 VLA workflow capability。
2. 新增 `VLAWorkflowPlan` 模型。
3. 新增导航场景模板。
4. 新增机械臂场景预留模板，状态为 unsupported/not implemented。
5. 新增导航数据画像模型。
6. 新增工具能力目录，从现有 `ToolSpec` registry 派生。
7. 新增 Plan-Agent prompt 和工具权限限制。
8. 新增 Executor-Agent prompt 和工具权限限制。
9. 新增确定性 `validate_plan` 节点。
10. 新增确定性 `update_state` 节点。
11. 接入现有导航 VLA 工具和 runtime。
12. 增加测试，覆盖导航计划生成、gridmap 变体、topic 工具变体、计划校验、执行
    路由和机械臂 unsupported 场景。

第一阶段不要求机械臂工具存在。系统只需要保证未来添加机械臂时，只需要：

```text
注册机械臂工具
补充机械臂场景模板
补充机械臂数据画像逻辑
增加对应测试
```

## 待确认的设计决策

实现前还需要确认以下问题：

1. `VLAWorkflowPlan` 保存为 YAML、JSON，还是两者都支持。
2. 是否所有执行计划都必须用户确认，还是只在包含写入/执行/长耗时步骤时确认。
3. Plan-Agent 和 Executor-Agent 是两个独立 AgentScope ReAct 实例，还是同一个
   ReAct wrapper 的两个 prompt profile。
4. LangGraph 放入哪个 optional dependency，例如 `multi_scene`、`vla_workflow` 或
   `langgraph`。
5. 当前 `DJSessionAgent` 是直接扩展，还是新增一个独立的 multi-scene session
   agent 来包装现有能力。

## 推荐落地路径

建议新增一个独立 capability 层：

```text
data_juicer_agents/capabilities/vla_workflow/
  graph.py
  state.py
  plan_agent.py
  executor_agent.py
  templates/
    navigation.yaml
    manipulation.yaml
  profile/
    navigation.py
  plan/
    model.py
    validate.py
```

这样可以保留当前单场景 VLA 工具和执行层，同时在其上方增加一个更结构化的多
场景 LangGraph 编排路径。
