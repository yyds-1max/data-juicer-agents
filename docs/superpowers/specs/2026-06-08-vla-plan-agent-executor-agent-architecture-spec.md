# VLA Plan-Agent 与 Executor-Agent 架构细化 Spec

日期：2026-06-08

## 1. 背景

当前仓库中的 VLA 数据处理能力已经接入了导航数据处理工具，现有执行方式主要依赖单个
ReAct session agent 在系统 prompt 中读取固定流程，然后按固定链路调用工具。

这个方式可以支撑当前导航原型，但不适合长期扩展。原因是：

- 未来会有多个处理场景，例如导航数据处理、机械臂数据处理等。
- 同一个场景下，不同日期、不同来源或不同脚本版本的数据形态可能不同。
- 数据形态差异会影响工具选择和流程选择，例如是否生成 grid_map、db3 topic 名是否匹配
  legacy 脚本默认 topic、是否已有 sync_data 或 annotation YAML。
- 这些差异不应继续硬编码在一个巨大的 session prompt 中，而应进入可审计的规划过程。

本 spec 细化多场景 VLA 架构中 Plan-Agent、Executor-Agent、数据画像、工具变体元数据、
workflow skeleton、planning notes 和 observations 的设计边界。

## 2. 总体方案

采用方案：

```text
文档驱动 + workflow skeleton 约束 + Tool 元数据硬约束
```

整体链路为：

```text
用户请求
  -> LangGraph 初始化状态
  -> Plan-Agent 识别场景
  -> Plan-Agent 读取场景规则 Markdown
  -> Plan-Agent 生成并保存 planning_notes.json
  -> Plan-Agent 调用专用检查工具，保存 observations.json
  -> Plan-Agent 填写 NavigationVLADataProfile
  -> 确定性节点校验 data_profile schema
  -> Plan-Agent 结合 workflow skeleton 和 Tool capability catalog 生成 VLAWorkflowPlan
  -> validate_plan 轻量校验
  -> 用户确认
  -> Executor-Agent 逐 stage 填参并调用工具
  -> Tool runtime 执行真实工具
  -> LangGraph 更新状态并路由
```

约束强度从弱到强为：

```text
用户目标
  < 场景规则 Markdown
  < Tool 元数据 / capability catalog
  < validate_plan 确定性校验
```

场景规则 Markdown 用于指导 Plan-Agent 理解业务差异；Tool 元数据声明系统真实可执行能力；
如果二者冲突，以 Tool 元数据为准。

## 3. Plan-Agent 职责

Plan-Agent 负责决定“应该做哪些处理步骤，以及每个步骤应该选择哪个工具或工具变体”。

Plan-Agent 采用 ReAct 范式，但它只能使用规划阶段允许的工具，例如：

- 读取场景规则文档的工具；
- 只读 inspection 工具；
- discovery/list 工具；
- dry-run 工具；
- 保存 planning_notes、observations、data_profile 和 plan 的工具；
- 查询 Tool capability catalog 的工具。

Plan-Agent 不允许直接执行真实长耗时处理脚本，不允许绕过 ToolSpec/runtime 直接 shell
执行数据处理代码。

Plan-Agent 的工作流程为：

```text
1. 根据用户请求识别 scenario。
2. 读取对应场景规则 Markdown。
3. 生成并保存 planning_notes.json。
4. 根据 planning_notes 判断还缺少哪些数据形态信息。
5. 每一步选择 Plan-Agent 专用检查工具进行检查。
6. 保存 observations.json，记录 raw_result 和 extracted_facts。
7. 当信息足够时，按预先设计好的 schema 填写 NavigationVLADataProfile。
8. 根据 data_profile、workflow skeleton 和 Tool capability catalog 生成 VLAWorkflowPlan。
9. 将 Plan 交给 validate_plan。
```

## 4. 场景规则 Markdown

每个处理场景维护一个主要由人编写的 Markdown 文档。该文档描述：

- 场景默认处理流程；
- 该场景中可能出现的数据形态差异；
- 不同数据形态通常应检查哪些信息；
- 不同数据形态可能对应哪些 stage 工具变体；
- 历史样本说明，例如 20270515 与 20270605 数据差异；
- 哪些现象不能作为硬编码规则，例如不能简单按日期决定 legacy 或 non-legacy。

Markdown 文档是 Plan-Agent 的规划指导，但不是执行准入依据。

如果 Markdown 建议使用某工具或 stage 变体，但 Tool capability catalog 中没有对应可用工具或
variant，则 Plan-Agent 不得生成可执行 stage，应在 data_profile 或 plan 中记录
blocking issue，例如 `doc_tool_conflict` 或 `missing_tool_variant`。

## 5. planning_notes.json

Plan-Agent 读取场景规则 Markdown 后，必须先保存 `planning_notes.json`，再继续调用检查
工具和生成 Plan。

`planning_notes.json` 是 Plan-Agent 对本次任务的规则理解与检查计划。它记录“我理解到
哪些规则，以及我接下来需要检查什么”，不记录真实检查结果。

建议结构：

```json
{
  "notes_id": "notes_20270605_navigation_001",
  "scenario": "navigation_vla",
  "source_docs": ["navigation_vla.md"],
  "user_inputs": {
    "date": "20270605",
    "scene_mode": "out"
  },
  "understood_rules": [
    {
      "id": "topic_schema_rule",
      "text": "如果 db3 topic 名与 legacy 默认 topic 不一致，应选择支持自定义 topic 或自适应 topic 的工具。"
    }
  ],
  "required_observations": [
    "ros2_topic_list",
    "topic_schema_type",
    "gridmap_generation",
    "available_script_variant"
  ],
  "unknowns": [
    "尚未检查 db3 topic 名。",
    "尚未判断是否会生成 grid_map。"
  ],
  "status": "need_inspection"
}
```

## 6. observations.json

Plan-Agent 每次调用检查工具后，都应保存 observation。

`observations.json` 同时保存：

- 工具返回的完整原始结果；
- Plan-Agent 从工具结果中提取出的关键事实；
- Plan-Agent 提取这些事实的理由；
- 这些事实用于支持哪些后续决策。

建议结构：

```json
{
  "observation_id": "obs_001",
  "tool": "vla_inspect_ros2_topics",
  "args": {
    "date": "20270605",
    "segment": "seg_a"
  },
  "raw_result": {
    "ok": true,
    "topics": [
      "/camera/front/image",
      "/rslidar_points",
      "/custom/odom"
    ]
  },
  "extracted_facts": {
    "topic_schema": "custom",
    "has_image_topic": true,
    "has_pointcloud_topic": true,
    "has_odom_topic": true,
    "matched_legacy_schema": false
  },
  "extraction_rationale": [
    "topic 列表包含必要 image/pointcloud/odom 类 topic。",
    "topic 名称与 legacy 默认 topic 不完全一致，因此标记为 custom。"
  ],
  "used_for": [
    "select_extract_and_sync_variant"
  ],
  "created_at": "2026-06-08T00:00:00Z"
}
```

这样后续排查时可以判断错误来源：

- 检查工具 raw_result 是否不完整；
- Plan-Agent 是否从 raw_result 中提取错了事实；
- Plan-Agent 是否误解了 Markdown 规则；
- Tool 元数据是否声明错误；
- validate_plan 是否没有拦住错误 Plan。

## 7. Plan-Agent 工作记忆

系统应为 Plan-Agent 额外设计工作记忆，并放在 LangGraph state 中，而不是只依赖
`planning_notes.json` 或 `observations.json`。

建议状态结构：

```json
{
  "scenario": "navigation_vla",
  "user_inputs": {},
  "source_docs": [],
  "planning_notes": {},
  "pending_observations": [],
  "observations": [],
  "data_profile_draft": {},
  "decisions": [],
  "unknowns": [],
  "ready_to_plan": false
}
```

Plan-Agent 每轮 ReAct 推理时，应读取这份 memory 的摘要或完整 JSON，使它知道：

- 已经读过哪些规则文档；
- 已经理解到哪些变化规则；
- 之前认为还缺少哪些信息；
- 已经调用过哪些检查工具；
- 每个工具查到了什么；
- 当前数据画像草稿已有字段；
- 哪些 unknowns 尚未解决。

`planning_notes.json` 和 `observations.json` 是可持久化快照与日志；PlanAgentMemory 是
规划过程中的活状态。

## 8. NavigationVLADataProfile

当前只为导航数据设计一种数据画像。暂不抽象 common/navigation 两层，也不提前为机械臂
场景设计字段。等机械臂数据和处理代码明确后，再重新优化跨场景抽象。

`NavigationVLADataProfile` 由 Plan-Agent 在获取足够 observations 后按预设 schema 填写。
确定性代码只负责 schema 校验、枚举值校验和必要字段检查，不负责自动生成画像。

建议字段（其中填写的参数仅是参考，重点看字段）：

```json
{
  "schema_version": 1,
  "scenario": "navigation_vla",

  "dataset": {
    "date": "20270605",
    "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
    "raw_date_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270605",
    "raw_work_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270605_temp",
    "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
    "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
    "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
    "scene_mode": "out",
    "selected_segments": ["20260605_152856", "20260605_152930"]
  },

  "raw_segments": [
    {
      "name": "20260605_152856",
      "path": "/media/heying/hy_data1/VLADatasets/raw_data/20270605_temp/20260605_152856",
      "has_db3": true,
      "has_metadata_yaml": true,
      "db3_files": ["20260605_152856_0.db3"],
      "duration_ns": 21872824365,
      "message_count": 17655
    }
  ],

  "topics": {
    "source_type": "ros2_db3",
    "raw_topics": [
      {
        "name": "/cam_video4/csi_cam/image_raw/compressed",
        "type": "sensor_msgs/msg/CompressedImage",
        "role": "front_fisheye_image",
        "canonical_dir": "fisheye_front",
        "message_count": 219
      },
      {
        "name": "/rs32_lidar_points",
        "type": "sensor_msgs/msg/PointCloud2",
        "role": "lidar",
        "canonical_dir": "r32_rslidar_points",
        "message_count": 218
      },
      {
        "name": "/sport_odom",
        "type": "nav_msgs/msg/Odometry",
        "role": "localization_odom",
        "canonical_dir": "odom",
        "message_count": 6308
      }
    ],
    "topic_schema": "go2w_current",
    "topic_mapping_variant": "cam4_rs32_sport_odom",
    "required_roles_present": true,
    "missing_required_roles": []
  },

  "sync": {
    "query_raw_dir": "rs32_lidar_points",
    "query_canonical_dir": "r32_rslidar_points",
    "output_dir": "sync_data",
    "sequence_suffix": "zhigu_wuhan"
  },

  "processing_state": {
    "has_raw_temp": true,
    "has_sync_data": false,
    "sync_data_segments": [],
    "has_finish_temp_samples": false,
    "has_annotation_yaml": false,
    "has_tracking_outputs": false,
    "has_final_outputs": false
  },

  "localization": {
    "source": "odom",
    "canonical_output": "Ins_compatible_odom",
    "requires_odom_convert": true,
    "requires_cp_ins": false
  },

  "calibration": {
    "platform_hint": "go2w",
    "sensor_params_dir": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01/NoobScenes/params/20260529_go2w/sensors",
    "sensor_params_status": "present"
  },

  "gridmap": {
    "raw_gridmap_topic_present": false,
    "gridmap_source": "existing_gridmap_artifact",
    "requires_gridmap_processing": true,
    "expect_gridmap_output": true,
    "reason": "final output expects grid_map and an existing grid_map artifact must be prepared before projection"
  },

  "stage_variants": {
    "extract_and_sync": {
      "variant": "go2w_current_topics",
      "reason": "raw topics match cam_video4 + rs32_lidar_points + sport_odom",
      "evidence": ["obs_raw_metadata_topics"]
    },
    "prepare_finish_dataset": {
      "variant": "go2w_20260529_sensor_params",
      "reason": "go2w sensor params directory is selected",
      "evidence": ["obs_run_odom_sensor_params"]
    },
    "build_noobscenes_inputs": {
      "variant": "odom_convert_resize",
      "reason": "localization source is odom and downstream scripts expect Ins-compatible odom",
      "evidence": ["obs_raw_metadata_topics"]
    },
    "gridmap_processing": {
      "variant": "copy_existing_artifact",
      "reason": "raw has no gridmap topic, but an existing grid_map artifact can be copied into the projection input location",
      "evidence": ["obs_gridmap_policy"]
    },
    "projection_and_trajectory": {
      "variant": "odom_cjl_0525_with_gridmap",
      "reason": "grid_map will be prepared by gridmap_processing and trajectory should use 2_othermethod_cjl_0525.py",
      "evidence": ["obs_run_odom_gridmap_steps"]
    },
    "validate_outputs": {
      "variant": "expect_gridmap",
      "reason": "gridmap.expect_gridmap_output is true",
      "evidence": ["obs_gridmap_policy"]
    }
  },

  "blocking_issues": [],
  "warnings": [],
  "evidence": {
    "dataset.raw_date_dir": ["obs_raw_date_dirs"],
    "dataset.raw_work_dir": ["obs_prepare_raw_temp"],
    "topics.topic_schema": ["obs_raw_metadata_topics"],
    "sync.query_raw_dir": ["obs_run_u_constants"],
    "sync.query_canonical_dir": ["obs_topic_mapping"],
    "gridmap.expect_gridmap_output": ["obs_run_odom_gridmap_steps"],
    "calibration.sensor_params_dir": ["obs_run_odom_sensor_params"]
  }
}
```

字段解释：

schema_version：数据画像 schema 版本，方便以后迁移。

scenario：场景类型。当前固定为 navigation_vla，用于选择导航 workflow skeleton。

dataset.date：处理日期，也是 clip/finish 目录组织的核心键。

dataset.raw_root：服务器原始数据根目录。

dataset.raw_date_dir：未准备前的日期目录，例如 /raw_data/20270605。

dataset.raw_work_dir：工具实际处理的工作目录，例如 /raw_data/20270605_temp。

dataset.clip_root：extract/sync 后的 clip 数据根目录。

dataset.finish_root：最终整理和轨迹产物根目录。

dataset.trajectory_root：服务器上的轨迹/标注/投影脚本根目录。

dataset.scene_mode：in 或 out，表示室内/室外，影响是否需要某些定位补充流程。

dataset.selected_segments：本次选择处理的 raw segment。

raw_segments：每个 raw segment 的可用性摘要，包括 db3、metadata、时长、消息数，用于确认输入是否足够。

topics.source_type：原始数据类型，当前为 ros2_db3。

topics.raw_topics：从 metadata/db3 中读出的 topic 列表，并归一到业务角色和 canonical 目录。

topics.raw_topics[].role：业务角色，如前视鱼眼、雷达、odom。Plan-Agent 用它判断必要输入是否齐全。

topics.raw_topics[].canonical_dir：同步后目录名，如 fisheye_front、r32_rslidar_points、odom。

topics.topic_schema：topic 组合类型，如 go2w_current、u_legacy、custom，决定 extract/sync 工具变体。

topics.topic_mapping_variant：更具体的 topic 映射方案名。

topics.required_roles_present：必要角色是否齐全。

topics.missing_required_roles：缺失的必要角色，非空时通常阻塞计划。

sync.query_raw_dir：同步脚本读取的原始拆包目录名，例如 rs32_lidar_points、lidar_points 或 grid_map。

sync.query_canonical_dir：同步后标准化目录名，例如 r32_rslidar_points，用于后续 finish/noobscenes 阶段。

sync.output_dir：同步结果目录名，当前通常为 sync_data。

sync.sequence_suffix：生成 clip 名称时追加的后缀，当前通常为 zhigu_wuhan。

processing_state：已有中间产物状态，用于决定 stage 是执行、跳过还是从中间恢复。

localization.source：定位来源，如 odom、ins、generated_ins。

localization.canonical_output：后续脚本期望的定位格式。

localization.requires_odom_convert：是否需要把 odom 转成 Ins-compatible 格式。

localization.requires_cp_ins：室内/特定平台是否需要复制建图得到的 Ins。

calibration.platform_hint：平台提示，如 go2w、u、shanmao，只作解释和辅助，不应作为唯一硬规则。

calibration.sensor_params_dir：本次要复制到 sample clip 下的 sensors 参数目录。

calibration.sensor_params_status：该目录是否存在、完整或未知。

gridmap.raw_gridmap_topic_present：raw db3 是否录了现成 gridmap topic。

gridmap.gridmap_source：最终 grid_map 来源，如 raw_topic、existing_gridmap_artifact、generated_from_pointcloud、unknown。

gridmap.requires_gridmap_processing：是否要执行 gridmap 处理工具。

gridmap.expect_gridmap_output：导航最终结果是否要求有 grid_map；导航场景第一版固定为 true，影响 move/validate 校验。

stage_variants：Plan-Agent 基于画像为有差异的 stage 推荐工具/脚本变体，并记录选择理由与 evidence。

blocking_issues：阻塞计划生成或执行的问题。

warnings：不阻塞但需要提醒用户或 Executor-Agent 注意的问题。

evidence：每个关键判断由哪些 observation 支撑，方便审计和排错。

Plan-Agent 需要工具查清的信息：

1.输入目录
检查 raw_root/date、raw_root/date_temp 是否存在；有哪些 segment；每个 segment 是否有 .db3 和 metadata.yaml。

2.ROS topic 画像
读取每个 segment 的 topic name、type、message_count、duration，并识别 image、lidar、odom、ins、gridmap 等业务角色。

3.Topic schema
判断 topic 组合属于 u_legacy、go2w_current、shanmao_ins、custom 还是 unknown，并产出 topic 到 canonical dir 的映射。

4.同步基准
判断 sync.query_raw_dir 应该用雷达、grid_map，还是其他低频稳定传感器，并确认对应的 sync.query_canonical_dir。

5.产物恢复状态
检查是否已有 clip_data/date/segment/sync_data、finish_data/date_temp/samples、annotation YAML、tracking 输出、最终 trajectory 输出。

6.定位来源
判断 raw 中是 odom 还是 Ins，是否需要 odom_convert，室内场景是否需要 cp_ins。

7.标定参数
根据 topic schema、平台和可用参数目录，判断应使用哪套 NoobScenes/params/.../sensors，并验证文件是否存在。

8.Gridmap 策略
判断 raw 是否有 gridmap topic、clip/sync 或中间目录下是否已有 grid_map、是否能从点云生成
grid_map；如果后续流程要求 grid_map，则决定是否需要执行独立的 gridmap_processing stage。

9.工具变体可用性
查询 Tool capability catalog，确认推荐的 extract/sync、prepare_finish、gridmap_processing、
projection、move、validate 变体是否真实可用。

10.阻塞与警告
如果缺 topic、缺 sensors、缺工具变体、gridmap 策略不明、selected segments 为空等，写入 blocking_issues 或 warnings。

## 9. Stage 变体选择

第一阶段不设计全局处理族字段。导航处理流程中大部分 stage 没有明显变体，如果强行引入全局
处理族标签，容易把少数 stage 的差异扩散成一套新的硬编码规则。

Plan-Agent 只在存在真实差异的 stage 上选择变体。整体数据形态由 `NavigationVLADataProfile`
解释，逐 stage 的选择理由由 `stage_variants` 记录。这样可以降低第一版开发复杂度，同时保留
审计和排错能力。

当前导航模板中，通常保持固定的 stage 包括：

```text
inspect_raw_date
check_runtime
prepare_raw_temp
list_clip_segments
manual_box_annotation
run_tracking
```

当前已知存在变体或参数差异的 stage 包括：

```text
extract_and_sync
  根据 topic_schema、topic_mapping_variant 和 sync.query_raw_dir 选择拆包/同步变体。

prepare_finish_dataset
  根据 calibration.sensor_params_dir 选择传感器参数目录，通常不需要拆成多个工具。

build_noobscenes_inputs
  根据 localization.source 选择 odom_convert、ins_native 或 indoor_cp_ins 等变体。

gridmap_processing
  根据 gridmap.raw_gridmap_topic_present、gridmap.gridmap_source 和
  gridmap.expect_gridmap_output 选择 copy_existing_artifact 或 pointcloud_to_gridmap。
  该 stage 的职责是把后续 projection 所需的 grid_map 准备到约定位置。
  导航场景最终要求 grid_map；只有 grid_map 已经存在于 projection 所需位置时，该 stage 可以跳过，
  并在 skipped_stages 中记录原因和 evidence。raw_gridmap_copy 作为未来 raw gridmap topic
  场景的预留变体。

projection_and_trajectory
  根据定位来源、gridmap 策略和可用脚本选择 odom_cjl_with_gridmap、
  odom_cjl_0525_with_gridmap，或未来预留的 Ins 相关 with_gridmap 变体。
  该 stage 只消费已经准备好的 grid_map，
  不负责生成或复制 grid_map。

validate_outputs
  导航场景使用 expect_gridmap，要求每个 final clip 都包含 grid_map。
```

选择规则：

```text
如果 topic_schema = unknown：
  Plan-Agent 不生成可执行 Plan，应继续检查 topic 或询问用户。

如果某 stage 没有变体：
  使用 workflow skeleton 中声明的默认工具和 default variant。

如果某 stage 有变体：
  使用 data_profile 中对应字段过滤 Tool capability catalog。
  根据 data_profile、Markdown文档和工具元数据选择变体。
  exact match 优先，其次 adaptive/custom variant。
  如果没有可用变体，记录 blocking_issue，不生成该 stage 的可执行计划。

如果数据形态与历史样本类似：
  可以在 reason 中说明类似样本，但不能仅按日期或样本名称选择变体。
```

第一版必须实现的变体：
```json
{
  "extract_and_sync": [
    "u_legacy_topics",
    "go2w_current_topics"
  ],
  "prepare_finish_dataset": [
    "u_20260409_sensor_params",
    "go2w_20260529_sensor_params"
  ],
  "build_noobscenes_inputs": [
    "odom_convert_resize"
  ],
  "gridmap_processing": [
    "copy_existing_artifact",
    "pointcloud_to_gridmap"
  ],
  "projection_and_trajectory": [
    "odom_cjl_with_gridmap",
    "odom_cjl_0525_with_gridmap"
  ],
  "validate_outputs": [
    "expect_gridmap"
  ]
}
```

第一版可选实现的变体：
```json
{
  "prepare_finish_dataset": [
    "custom_sensor_params"
  ],
  "projection_and_trajectory": [
    "odom_cjl_with_gridmap"
  ]
}
```

预留但第一版不实现的变体：
```json
{
  "gridmap_processing": [
    "raw_gridmap_copy"
  ],
  "projection_and_trajectory": [
    "ins_*"
  ],
  "build_noobscenes_inputs": [
    "ins_native",
    "indoor_cp_ins"
  ]
}
```



## 10. Tool capability catalog

系统应在现有 ToolSpec 基础上补充 VLA 工具能力元数据。基础 ToolSpec 已有：

- name；
- description；
- input schema；
- output schema；
- tags；
- effects；
- confirmation。

VLA 扩展元数据第一版采用“统一外壳 + stage/variant 专用扩展”的结构。

统一外壳用于支撑 Tool capability catalog、Plan-Agent 工具过滤、`validate_plan`
轻量校验和 Executor-Agent 基础填参。不同 `stage_kind` 或不同 variant 的业务差异，
放入 `variants[].stage_config` 中。

建议统一结构如下：

```json
{
  "tool": "vla_extract_and_sync",
  "scenario": "navigation_vla",
  "stage_kind": "extract_and_sync",
  "implementation_status": "available",
  "supports_dry_run": true,
  "plan_agent_allowed": false,
  "executor_agent_allowed": true,
  "variants": [
    {
      "id": "u_legacy_topics",
      "status": "available",
      "selectors": {
        "topic_schema": ["u_legacy"]
      },
      "arg_bindings": {
        "date": "dataset.date",
        "selected_segments": "dataset.selected_segments",
        "raw_root": "dataset.raw_root",
        "clip_root": "dataset.clip_root",
        "query_dir": "sync.query_raw_dir"
      },
      "preconditions": [
        {
          "type": "path_exists",
          "path": "dataset.raw_work_dir"
        },
        {
          "type": "non_empty",
          "path": "dataset.selected_segments"
        }
      ],
      "expected_artifacts": [
        {
          "kind": "directory",
          "path_template": "{clip_root}/{date}/{segment}/sync_data",
          "required": true
        }
      ],
      "recoverable_errors": [
        {
          "type": "missing_raw_segments",
          "suggested_action": "rerun_prepare_raw_temp_or_reselect_segments"
        }
      ],
      "stage_config": {
        "topic_schema_support": ["u_legacy"],
        "supports_custom_topic_mapping": false
      }
    },
    {
      "id": "go2w_current_topics",
      "status": "available",
      "selectors": {
        "topic_schema": ["go2w_current"]
      },
      "arg_bindings": {
        "date": "dataset.date",
        "selected_segments": "dataset.selected_segments",
        "raw_root": "dataset.raw_root",
        "clip_root": "dataset.clip_root",
        "query_dir": "sync.query_raw_dir"
      },
      "expected_artifacts": [
        {
          "kind": "directory",
          "path_template": "{clip_root}/{date}/{segment}/sync_data",
          "required": true
        }
      ],
      "stage_config": {
        "topic_schema_support": ["go2w_current"],
        "supports_custom_topic_mapping": false
      }
    }
  ]
}
```

统一字段说明：

- `tool`：真实注册的 ToolSpec 名称。
- `scenario`：该工具能力适用的场景。
- `stage_kind`：该工具在 workflow skeleton 中对应的阶段类型。
- `implementation_status`：工具整体状态，可取 `available`、`planned`、`placeholder` 或 `deprecated`。
- `supports_dry_run`：该工具是否支持只生成计划而不执行真实处理。
- `plan_agent_allowed`：Plan-Agent 是否可以调用该工具。真实写入/执行类工具通常为 false。
- `executor_agent_allowed`：Executor-Agent 是否可以在已确认计划中调用该工具。
- `variants`：该工具支持或计划支持的变体列表。`supported_variants` 不单独维护，由 `variants[].id` 派生。
- `variants[].status`：该变体状态，可取 `available`、`planned`、`placeholder` 或 `deprecated`。
- `variants[].selectors`：Plan-Agent 选择该变体时参考的数据画像条件。
- `variants[].arg_bindings`：Executor-Agent 从 data_profile、observations、previous_stage_outputs 或 runtime_context 中读取参数的位置。
- `variants[].preconditions`：执行该变体前应满足的轻量前置条件。
- `variants[].expected_artifacts`：该变体预期产物，供 resume、skip 和 validate 使用。
- `variants[].recoverable_errors`：可恢复错误及建议动作。
- `variants[].stage_config`：该 `stage_kind` 或 variant 的专用业务配置。

`stage_config` 不要求所有工具使用同一套字段。第一版只约定它是一个结构化对象，
具体字段在开发对应 `stage_kind` 或 variant 时再设计。例如：

```json
{
  "extract_and_sync": {
    "topic_schema_support": ["u_legacy", "go2w_current"],
    "supports_custom_topic_mapping": false,
    "requires_query_raw_dir": true
  },
  "projection_and_trajectory": {
    "trajectory_script": "2_othermethod_cjl_0525.py",
    "move_script": "3_move_dir.py",
    "requires_gridmap": true
  },
  "gridmap_processing": {
    "tool": "vla_prepare_gridmap",
    "preparation_modes": ["copy_existing_artifact", "pointcloud_to_gridmap"],
    "output_contract": "grid_map is available at the projection input path before projection_and_trajectory starts"
  },
  "prepare_finish_dataset": {
    "sensor_params_policy": "explicit_path",
    "required_canonical_dirs": ["fisheye_front", "r32_rslidar_points"]
  }
}
```

也就是说，系统层面只依赖统一外壳做通用判断；业务层面的精确选择规则留在
`stage_config` 中，并在具体实现该 stage 时补充 schema、枚举值和测试。

Tool 元数据是执行准入依据。如果 Markdown 文档和 Tool 元数据冲突，以 Tool 元数据为准。
第一版 Tool capability catalog 必须包含 `vla_prepare_gridmap`，其 `stage_kind` 为
`gridmap_processing`，并至少支持 `copy_existing_artifact` 和 `pointcloud_to_gridmap`
两个 available variant。

## 11. Workflow skeleton

workflow skeleton 是场景流程骨架，不负责生成工具参数。

它提供：

- 标准 stage_kind 顺序；
- 每个 stage_kind 允许的工具或工具变体集合；
- 人工 checkpoint 位置；
- 哪些 stage 可以因为 data_profile 被跳过或替换。

导航 skeleton 示例：

```json
{
  "scenario": "navigation_vla",
  "stage_order": [
    "inspect_raw_date",
    "check_runtime",
    "prepare_raw_temp",
    "extract_and_sync",
    "list_clip_segments",
    "prepare_finish_dataset",
    "build_noobscenes_inputs",
    "manual_box_annotation",
    "run_tracking",
    "gridmap_processing",
    "projection_and_trajectory",
    "validate_outputs"
  ],
  "human_checkpoints": [
    {
      "stage_kind": "manual_box_annotation",
      "type": "gui_annotation"
    }
  ],
  "variant_source": "tool_capability_catalog",
  "skip_policy": {
    "allowed": true,
    "must_record": ["reason", "evidence"]
  }
}
```

Plan-Agent 可以根据 observations、data_profile、markdown的指导和用户提示跳过某些 stage，但必须记录跳过原因。
`gridmap_processing` 是可执行 stage：当最终要求 `grid_map` 且需要复制已有 artifact 或从点云生成时，
应进入 `active_stages`；当 `grid_map` 已经位于 projection 所需输入位置时，
可以跳过并记录依据。

## 12. VLAWorkflowPlan

`VLAWorkflowPlan` 只描述调用工具的流程，不包含具体工具参数。

Plan-Agent 负责生成：

- stage 顺序；
- stage_kind；
- tool；
- variant；
- effects；
- skipped_stages。

Plan-Agent 不负责生成：

- 每个工具的具体 args；
- 来自前序 stage 输出的参数绑定；
- runtime 具体路径推导。

示例：

```json
{
  "plan_id": "vla_plan_20270605_001",
  "scenario": "navigation_vla",
  "status": "pending",
  "planning_notes_ref": "planning_notes.json",
  "observations_ref": "observations.json",
  "data_profile_ref": "data_profile.json",
  "active_stages": [
    {
      "id": "inspect_raw_date",
      "stage_kind": "inspect_raw_date",
      "tool": "vla_inspect_raw_date",
      "variant": "default",
      "effects": "read"
    },
    {
      "id": "extract_and_sync",
      "stage_kind": "extract_and_sync",
      "tool": "vla_extract_and_sync",
      "variant": "go2w_current_topics",
      "effects": "execute",
      "decision_ref": "data_profile.stage_variants.extract_and_sync"
    },
    {
      "id": "gridmap_processing",
      "stage_kind": "gridmap_processing",
      "tool": "vla_prepare_gridmap",
      "variant": "pointcloud_to_gridmap",
      "effects": "execute",
      "decision_ref": "data_profile.stage_variants.gridmap_processing"
    },
    {
      "id": "projection_and_trajectory",
      "stage_kind": "projection_and_trajectory",
      "tool": "vla_run_projection_and_trajectory",
      "variant": "odom_cjl_0525_with_gridmap",
      "effects": "execute",
      "decision_ref": "data_profile.stage_variants.projection_and_trajectory"
    },
    {
      "id": "validate_outputs",
      "stage_kind": "validate_outputs",
      "tool": "vla_validate_outputs",
      "variant": "expect_gridmap",
      "effects": "read",
      "decision_ref": "data_profile.stage_variants.validate_outputs"
    }
  ],
  "skipped_stages": [
    {
      "stage_kind": "manual_box_annotation",
      "reason": "annotation YAML already exists for all selected clips",
      "evidence": ["obs_006"],
      "source": "previous_artifacts"
    }
  ]
}
```

Plan-Agent 可以跳过 stage，但必须把被跳过的 stage 写入 `skipped_stages`，并至少记录
`reason`。
如果跳过 `gridmap_processing`，原因应明确说明是最终不要求 `grid_map`，还是 `grid_map`
已经存在于 projection 所需输入位置。

## 13. validate_plan

第一版 `validate_plan` 只做轻量校验，目标是防止 Plan-Agent 编造工具或随意改变主流程。

校验内容：

```text
1. active_stages 顺序是否合法。
2. active_stages 中的 tool 是否存在。
3. active_stages 中的 variant 是否被该 tool 的元数据支持。
4. skipped_stages 中如果存在跳过步骤，则检验跳过原因、evidence是否缺失
```

`validate_plan` 暂不负责：

- 校验工具参数；
- 判断参数是否可从 data_profile / observations / previous_stage_outputs / runtime_context 推导；
- 判断每个 stage 是否一定能执行成功；
- 执行复杂业务规则推理。

如果 skipped_stages 中存在跳过原因缺失、evidence 缺失，validate_plan 可以返回 warning。

## 14. Executor-Agent 职责

Executor-Agent 负责按 Plan 执行当前 stage。第一版应尽量复用当前仓库中
`DJSessionAgent + ReActAgent + Toolkit + ToolSpec runtime` 的工具调用链，只把流程来源
从 session prompt 中的固定自然语言链路，改成 LangGraph 选出的结构化 `current_stage`。

Executor-Agent 不重新读取场景规则 Markdown，不重新设计流程，不替换 Plan-Agent 已选择的工具
或 variant。完整流程顺序由 LangGraph 的 `select_next_stage` 控制；Executor-Agent 每次只处理
一个 stage。

第一版建议把 Executor-Agent 实现为一个受限的 ReAct profile：

```text
输入：
  current_stage
  data_profile
  observations
  previous_stage_outputs
  runtime_context
  tool_capability
  tool_input_schema

能力：
  只暴露 current_stage.tool 对应的 ToolSpec 工具。
  不暴露同场景的其他执行工具，避免 Executor-Agent 自行换工具。

输出：
  stage_result
```

Executor-Agent 填参依据为：

```text
current_stage
data_profile
observations
previous_stage_outputs
runtime_context
tool_capability
tool_input_schema
```

其中 `tool_capability` 提供当前 tool/variant 的元数据，例如 selectors、arg_bindings、
preconditions、expected_artifacts 和 recoverable_errors。Executor-Agent 填参时应优先参考工具
元数据和当前 stage，而不是自由猜测。

Executor-Agent 可以：

- 根据当前 stage 的 tool input schema 填写 args；
- 调用当前 stage 指定工具；
- 解读工具返回结果；
- 在允许范围内重试；
- 请求 replan；
- 总结当前 stage 状态。

Executor-Agent 不可以：

- 改变 stage 顺序；
- 换工具或 variant；
- 插入 Plan 中没有的 stage；
- 重新解释场景规则 Markdown；
- 使用 shell 绕过 ToolSpec/runtime 执行真实数据处理。

第一版不强制把 `prepare_args`、`validate_tool_args`、`invoke_tool_runtime` 拆成多个独立
LangGraph 节点。可以在 `executor_agent_execute_stage` 节点内部复用当前工具调用机制：

```text
Executor-Agent ReAct 填写 args
  -> 调用 current_stage.tool
  -> ToolSpec/Pydantic 校验 input args
  -> Tool runtime 执行
  -> Executor-Agent 解读 tool result
  -> 返回 stage_result
```

当前 AgentScope tool adapter 和 `ToolSpec.execute()` 已经会通过 Pydantic input model 校验工具
参数，并在参数错误时返回 `invalid_arguments`。因此第一版可以把参数校验视为工具调用入口的一
部分。未来如果需要更强控制，再拆出显式的 `executor_agent_prepare_args`、`validate_tool_args`
和 `invoke_tool_runtime` 节点。

Executor-Agent 返回的 `stage_result` 应是结构化结果，建议包含：

```json
{
  "stage_id": "projection_and_trajectory",
  "stage_kind": "projection_and_trajectory",
  "tool": "vla_run_projection_and_trajectory",
  "variant": "odom_cjl_0525_with_gridmap",
  "status": "success",
  "tool_args_preview": {},
  "tool_result": {},
  "artifacts": [],
  "error_type": "",
  "next_action": "continue",
  "summary": ""
}
```

`update_state` 将 `stage_result` 写入 LangGraph state，后续 stage 通过
`previous_stage_outputs` 使用这些结构化结果。

`status` 建议使用以下枚举：

```text
success
failed
needs_user
needs_replan
interrupted
```

`next_action` 建议使用以下枚举：

```text
continue
retry
pause
replan
stop
```

实时反馈方面，第一版保留当前 ReAct session 的 Agent/Stage 级反馈体验即可，不要求长耗时脚本
执行过程中的 stdout/stderr 流式反馈。应保留或新增以下事件：

```text
stage_selected
executor_reasoning_step
tool_start
tool_end
stage_summary
route_after_stage
replan_requested
```

现有 `event_callback`、ReAct reasoning hook、`tool_start` 和 `tool_end` 事件可以继续复用。长耗时
脚本内部进度第一版不做实时展示，工具完成后返回结构化结果和日志路径即可。

## 15. LangGraph 编排

建议 LangGraph 外层节点为：

```text
user_request
  -> plan_agent_read_docs
  -> save_planning_notes
  -> plan_agent_inspect_loop
  -> save_observations
  -> plan_agent_fill_data_profile
  -> validate_data_profile
  -> generate_workflow_plan
  -> validate_plan
  -> ask_confirmation
  -> select_next_stage
  -> executor_agent_execute_stage
  -> update_state
  -> route_after_stage
  -> select_next_stage
  -> ...
  -> final_summary
```

其中：

- Plan-Agent 子流程负责规划和数据画像；
- Executor-Agent 子流程负责逐 stage 执行；
- validate_plan、select_next_stage、update_state、route_after_stage 是确定性节点；
- 第一版参数校验复用 ToolSpec/Pydantic 工具入口，未来可按需拆出独立 `validate_tool_args` 节点。

## 16. 建议给 Plan-Agent 补充的专用检查工具清单：
这些工具都是read-only，不需要 dry-run。

1. vla_inspect_raw_layout
检查 raw_root/date、raw_root/date_temp、segment 列表、每个 segment 的 .db3、metadata.yaml、db3 主文件大小、是否有 SQLite -shm/-wal 辅助文件。
填充：dataset、raw_segments、processing_state.has_raw_temp。

2. vla_inspect_rosbag_metadata
解析 metadata.yaml，必要时 fallback 到 db3 sqlite，输出 topic name/type/message_count/duration。
填充：topics.raw_topics、raw_segments.duration_ns、raw_segments.message_count。

3. vla_classify_navigation_topic_schema
根据真实 topic 组合识别 u_legacy、go2w_current、shanmao_ins、custom、unknown，并产出 canonical 映射。
填充：topics.topic_schema、topics.topic_mapping_variant、topics.required_roles_present、topics.missing_required_roles。

4. vla_infer_sync_policy
根据 topic schema 和低频基准候选判断 sync.query_raw_dir / sync.query_canonical_dir，例如 lidar_points -> r32_rslidar_points 或 rs32_lidar_points -> r32_rslidar_points。
填充：sync、stage_variants.extract_and_sync。

5. vla_inspect_datatoolbox_variants
读取服务器 DataToolbox 脚本，检查 whitelist、topic_map、legacy/current 脚本是否存在，确认某个 topic schema 是否真的有可用脚本变体。
填充：stage_variants.extract_and_sync，缺变体时写 blocking_issues。

6. vla_inspect_processing_state
检查 clip_data/date/segment/sync_data、finish_data/date_temp/samples、annotation YAML、tracking 输出、project_npy、final trajectory 输出。
填充：processing_state，并支持 Plan-Agent 判断哪些 stage 可跳过。

7. vla_inspect_calibration_assets
列出 NoobScenes/params/*/sensors，校验 fisheye_front.json、r32_rslidar_points.json 是否存在，并读取 sensor json 的 target/camera 参数摘要。
填充：calibration、stage_variants.prepare_finish_dataset。

8. vla_infer_localization_policy
根据 topic 里是 odom 还是 Ins 判断是否需要 1_odom_convert.py，室内场景是否可能需要 cp_ins.py。
填充：localization、stage_variants.build_noobscenes_inputs。

9. vla_inspect_gridmap_artifacts
同时检查三件事：raw topic 是否有 gridmap、clip/sync 或中间目录下是否已有 grid_map、是否具备
从点云生成 grid_map 的可用工具变体。
填充：gridmap.raw_gridmap_topic_present、gridmap.gridmap_source、gridmap.available_gridmap_artifacts、
gridmap.requires_gridmap_processing、stage_variants.gridmap_processing、evidence。
如果最终要求 `grid_map`，但既没有现成 artifact，也没有可用生成工具，则写入 blocking_issues；
如果生成工具可用，则 `gridmap.gridmap_source` 可以为 `generated_from_pointcloud`，并推荐
`gridmap_processing=pointcloud_to_gridmap`。

10. vla_inspect_trajectory_script_variants
检查 2_pt_project 下的 2_othermethod_cjl.py、2_othermethod_cjl_0525.py、3_move_dir.py 是否存在，并声明 move 脚本要求 gridmap。
填充：available_script_variants、tool_capability_evidence、blocking_issues / warnings。

11. vla_list_tool_capability_catalog
从 ToolSpec registry + VLA 扩展元数据返回 tool、scenario、stage_kind、effects、implementation_status、
plan_agent_allowed、executor_agent_allowed，以及 variants[].id/status/selectors。
用于防止 Plan-Agent 选择不存在的变体。

12. vla_validate_navigation_data_profile
确定性校验 NavigationVLADataProfile：必要字段、枚举值、evidence 引用、关键字段内部一致性，
例如 topic_schema 与 stage_variants 中的推荐变体是否矛盾，gridmap 字段与推荐的 gridmap/projection/validate 变体是否矛盾。


## 17. 需要继续讨论确定的设计点

以下设计点仍需进一步讨论，本 spec 暂不最终定案：

1. **持久化与日志目录**
   - planning_notes.json、observations.json、data_profile.json、plan.json 的保存路径；
   - run_id 生成规则；
   - 是否每次 replan 生成新版本。

2. **测试策略**
    - 如何构造 20270515 无 grid_map 样例；
    - 如何构造 20270605 custom topic 样例；
    - 如何测试 Markdown 与 Tool 元数据冲突；
    - 如何测试 Plan-Agent 跳过 stage 的记录；
    - 如何测试 Executor-Agent 不重新改工具和流程。

## 18. 当前已明确的设计结论

本轮讨论已经确定：

1. 选择“文档驱动 + workflow skeleton 约束 + Tool 元数据硬约束”方案。
2. 场景规则文档主要由人维护成 Markdown 自然语言文档。
3. Plan-Agent 读取 Markdown 后必须先保存 `planning_notes.json`。
4. Plan-Agent 后续检查结果保存到 `observations.json`。
5. observations 同时保存 raw_result 和 extracted_facts。
6. 系统为 Plan-Agent 额外设计 LangGraph state 工作记忆。
7. 当前只设计导航数据的 `NavigationVLADataProfile`，暂不抽象机械臂。
8. `NavigationVLADataProfile` 的第一版字段已确定，包含 dataset、raw_segments、topics、sync、processing_state、localization、calibration、gridmap、stage_variants、blocking_issues、warnings 和 evidence。
9. 第一版不设计全局处理族字段；Plan-Agent 只在有真实差异的 stage 上选择工具变体。
10. Tool 元数据优先于 Markdown 文档。
11. Tool capability catalog 第一版采用“统一外壳 + stage/variant 专用扩展”的结构，variant 细节放在 `variants[].stage_config` 中。
12. Workflow skeleton 第一版只约束 stage 顺序、人工 checkpoint 位置、variant 来源和 skip 记录规则，不维护 required_stages / optional_stages。
13. `VLAWorkflowPlan` 只包含流程、工具和 variant，不包含工具 args，不保存 checkpoint；第一版使用 `active_stages + skipped_stages`。
14. Executor-Agent 根据 current_stage、data_profile、observations、previous_stage_outputs、runtime_context、tool_capability 和 tool_input_schema 填 args。
15. Executor-Agent 不重新读取场景规则 Markdown。
16. Executor-Agent 第一版复用当前 ReAct 工具调用链，实现为单 stage、受限 toolkit 的 ReAct profile。
17. `validate_plan` 第一版只校验 stage 顺序、tool 是否存在、variant 是否被工具元数据支持，并对 skipped_stages 的 reason/evidence 缺失返回 warning。
18. Plan-Agent 可以跳过 stage，但必须在 Plan 中记录跳过原因。
19. `gridmap_processing` 是导航 workflow 中可执行的独立 stage，放在 `run_tracking` 之后、`projection_and_trajectory` 之前；`vla_prepare_gridmap` 负责复制已有 grid_map artifact 或从点云生成 grid_map，`projection_and_trajectory` 只消费已准备好的 grid_map，不负责生成或复制。
20. Plan-Agent 专用检查工具清单。
21. 导航场景 Markdown 文档结构
