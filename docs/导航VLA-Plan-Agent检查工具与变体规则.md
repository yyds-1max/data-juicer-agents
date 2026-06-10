# 导航 VLA Plan-Agent 检查工具与变体选择规则

日期：2026-06-09

## 1. 文档定位

本文档用于指导 Plan-Agent 在导航 VLA 数据处理场景中先检查数据形态，再选择处理流程和工具变体。

Plan-Agent 读取本文档后，应产出 `planning_notes.json`，随后调用只读检查工具生成 `observations.json`，再填写 `NavigationVLADataProfile`，最后结合 workflow skeleton 与 Tool capability catalog 生成 `VLAWorkflowPlan`。

本文档只负责描述业务规则、历史样本差异、应检查的信息和变体选择依据。它不负责：

- 证明某个工具真实存在；
- 代替 ToolSpec input schema；
- 代替 Tool capability catalog；
- 代替 `validate_plan`；
- 授权执行长耗时、写文件或人工标注步骤；
- 按日期硬编码处理流程。

如果本文档与 Tool capability catalog 冲突，以 Tool capability catalog 为准。Plan-Agent 不得为了贴合本文档而编造工具或变体。

## 2. 禁止硬编码规则

Plan-Agent 不得用日期直接判断数据类型。例如不能写成：

```text
date == 20270515 -> 使用 legacy 流程
date == 20270605 -> 使用 go2w 流程
```

日期只能作为样本标签、目录键和日志字段。真正的判断必须来自检查工具返回的事实：

- raw segment 是否存在；
- metadata.yaml / db3 是否存在；
- ROS topic name、type、message_count、duration；
- image、lidar、odom、Ins、gridmap 等业务角色是否齐全；
- topic 到标准目录名的映射是否明确；
- 同步基准目录是否存在；
- clip / finish 中间产物是否已经存在；
- NoobScenes 标定参数目录是否存在且内容完整；
- grid_map 是 raw topic、已有 clip artifact、点云生成结果，还是不存在；
- 当前仓库 ToolSpec 是否支持推荐的工具变体。

历史样本可以作为规则设计的证据，但不能作为 Plan-Agent 的判定条件。

## 3. 已观察到的历史样本差异

### 3.1 样本 A：`20270515`

本地样本路径：

```text
我的数据处理流/VLADatasets/raw_data/20270515
```

服务器对应路径按系统默认根目录表达为：

```text
/media/heying/hy_data1/VLADatasets/raw_data/20270515
```

已观察事实：

- raw segment 包含 `20260515_102948`、`20260515_103111`。
- 每个 segment 包含 `.db3` 和 `metadata.yaml`。
- db3 旁边存在 `*.db3-shm`、`*.db3-wal` 辅助文件。这是 SQLite 存储状态差异，不应作为处理族判据。
- metadata 版本为 rosbag2 metadata version 4。
- 主要 topic 组合为：
  - `/cam_video5/csi_cam/image_raw/compressed`，角色为前视鱼眼图像；
  - `/lidar_points`，角色为雷达点云；
  - `/utlidar/robot_odom_systime`，角色为 odom 定位；
  - `/sport_imu`，辅助 IMU。
- raw metadata 中未观察到 `/drivers/ins/Ins`。
- raw metadata 中未观察到 gridmap topic。

对应脚本证据：

- legacy 拆包脚本白名单包含 `/cam_video5/csi_cam/image_raw/compressed`、`/lidar_points`、`/utlidar/robot_odom_systime`。
- legacy 同步脚本映射为：
  - `cam_video5 -> fisheye_front`
  - `lidar_points -> r32_rslidar_points`
  - `utlidar -> odom`
- 旧 `run_U.sh` 使用 `sync_query_dir="lidar_points"`。
- 旧 `run_odom.sh` 复制 `NoobScenes/params/20260409_U/sensors`。
- 旧 `run_odom.sh` 执行 `1_odom_convert.py` 和 `2_resize.py`。
- 旧 `run_odom.sh` 注释说明当前测试数据不生成 raw gridmap topic，并跳过 `cp_gridmap.py`；该注释不能解释为最终产物不需要 `grid_map`。
- 旧 `run_odom.sh` 使用 `2_othermethod_cjl.py`。
- 旧 `run_odom.sh` 最后仍调用 `3_move_dir.py`，该脚本要求复制 `grid_map`。如果 raw 没有 gridmap topic，Plan-Agent 应先查找 clip/sync artifact 或调用点云生成 gridmap 工具；两者都不可用时阻塞，不能降级为 no-gridmap move/validate。

推荐画像标签：

```text
topic_schema = u_legacy_topics
topic_mapping_variant = cam5_lidar_points_utlidar_odom
sync.query_raw_dir = lidar_points
sync.query_canonical_dir = r32_rslidar_points
localization.source = odom
localization.requires_odom_convert = true
gridmap.raw_gridmap_topic_present = false
gridmap.expect_gridmap_output = true
gridmap.gridmap_source = existing_gridmap_artifact 或 generated_from_pointcloud
```

### 3.2 样本 B：`20270605`

本地样本路径：

```text
我的数据处理流/VLADatasets/raw_data/20270605
```

服务器对应路径按系统默认根目录表达为：

```text
/media/heying/hy_data1/VLADatasets/raw_data/20270605
```

已观察事实：

- raw segment 包含 `20260605_152856`、`20260605_152930`。
- 每个 segment 包含 `.db3` 和 `metadata.yaml`。
- metadata 版本为 rosbag2 metadata version 5。
- 主要 topic 组合为：
  - `/cam_video4/csi_cam/image_raw/compressed`，角色为前视鱼眼图像；
  - `/rs32_lidar_points`，角色为雷达点云；
  - `/sport_odom`，角色为 odom 定位；
  - `/sport_imu`，辅助 IMU。
- raw metadata 中未观察到 `/drivers/ins/Ins`。
- raw metadata 中未观察到 gridmap topic。

对应脚本证据：

- 当前服务器 DataToolbox 拆包脚本白名单包含 `/cam_video4/csi_cam/image_raw/compressed`、`/rs32_lidar_points`、`/sport_odom`。
- 当前服务器同步脚本映射为：
  - `cam_video4 -> fisheye_front`
  - `rs32_lidar_points -> r32_rslidar_points`
  - `sport_odom -> odom`
- 当前服务器 `run_U.sh` 使用 `sync_query_dir="rs32_lidar_points"`。
- 当前服务器 `run_odom.sh` 复制 `NoobScenes/params/20260529_go2w/sensors`。
- 当前服务器 `run_odom.sh` 执行 `1_odom_convert.py` 和 `2_resize.py`。
- 当前服务器 `run_odom.sh` 执行 `cp_gridmap.py`。
- 当前服务器 `run_odom.sh` 使用 `2_othermethod_cjl_0525.py`。
- 当前服务器 `run_odom.sh` 使用 `3_move_dir.py`，该脚本要求最终复制 `grid_map`。
- `cp_gridmap.py` 从 `/media/heying/hy_data1/VLADatasets/clip_data/<date>/<segment>/sync_data/<clip>/grid_map` 查找已有 grid_map，再复制到 finish temp。它不是从 raw db3 直接生成 gridmap。

推荐画像标签：

```text
topic_schema = go2w_current_topics
topic_mapping_variant = cam4_rs32_sport_odom
sync.query_raw_dir = rs32_lidar_points
sync.query_canonical_dir = r32_rslidar_points
localization.source = odom
localization.requires_odom_convert = true
gridmap.raw_gridmap_topic_present = false
gridmap.expect_gridmap_output = true，仅当 clip/sync 已有 grid_map 或可用 gridmap 生成工具存在
```

如果 raw 没有 gridmap topic，clip/sync 也没有 grid_map，且 Tool capability catalog 中没有 pointcloud-to-gridmap 工具，则 Plan-Agent 必须记录 blocking issue：`missing_gridmap_source_or_generator`。

## 4. 导航数据核心判断轴

Plan-Agent 应围绕以下判断轴建立数据画像。

### 4.1 Topic schema

Topic schema 由 topic 组合决定，不由日期或平台名直接决定。

当前已知 schema：

| schema | 必要 topic 事实 | 标准目录映射 | 典型同步基准 |
| --- | --- | --- | --- |
| `u_legacy_topics` | `/cam_video5/csi_cam/image_raw/compressed` + `/lidar_points` + `/utlidar/robot_odom_systime` | `cam_video5 -> fisheye_front`，`lidar_points -> r32_rslidar_points`，`utlidar -> odom` | `lidar_points` |
| `go2w_current_topics` | `/cam_video4/csi_cam/image_raw/compressed` + `/rs32_lidar_points` + `/sport_odom` | `cam_video4 -> fisheye_front`，`rs32_lidar_points -> r32_rslidar_points`，`sport_odom -> odom` | `rs32_lidar_points` |
| `shanmao_ins_topics` | 前视鱼眼 + 雷达 + `/drivers/ins/Ins` | 需要由检查工具确认 | 通常为雷达或 gridmap |
| `custom_topics` | 必要业务角色齐全，但 topic 名不匹配已知 schema | 必须由用户或配置提供 topic mapping | 由检查工具推断 |
| `unknown_topics` | 必要业务角色不齐全，或无法映射 | 无 | 阻塞 |

如果必要业务角色缺失，Plan-Agent 不得继续生成可执行处理计划。

### 4.2 定位来源

导航流程下游 NoobScenes 和标注相关脚本历史上依赖 Ins/odom 兼容目录。Plan-Agent 必须区分：

| localization.source | 条件 | 处理策略 |
| --- | --- | --- |
| `odom` | raw topic 包含 Odometry，例如 `/utlidar/robot_odom_systime` 或 `/sport_odom` | 需要 `1_odom_convert.py`，将 odom 转为下游可用格式 |
| `ins` | raw topic 包含 `/drivers/ins/Ins`，且下游脚本按 Ins 读取 | 不应执行 odom_convert；选择 `ins_native` 变体 |
| `generated_ins` | 室内或特定平台需要从建图结果复制 Ins | 选择 `indoor_cp_ins` 变体；必须检查 `cp_ins.py` 和建图产物 |
| `unknown` | 无 odom/Ins 或无法判断 | 阻塞 |

当前仓库的 `vla_build_noobscenes_inputs` 会固定执行 `1_odom_convert.py` 和 `2_resize.py`。如果数据画像为 `ins` 或 `generated_ins`，Plan-Agent 必须检查 Tool capability catalog 是否已有对应变体；没有时记录 `missing_localization_variant`。

### 4.3 Gridmap 策略

Plan-Agent 必须把 gridmap 分成三个问题检查：

1. raw db3 是否录制了 gridmap topic；
2. clip/sync 中是否已有 `grid_map` artifact；
3. 当前工具目录是否有从点云生成 gridmap 的工具变体。

可选策略：

| gridmap_source | 条件 | 处理策略 |
| --- | --- | --- |
| `raw_topic` | raw topic 有 gridmap，且拆包/同步工具支持 | 拆包并同步 gridmap，后续 `use_gridmap=true` |
| `existing_gridmap_artifact` | clip/sync 下已有 `grid_map` | 执行 `cp_gridmap.py`，后续 `use_gridmap=true` |
| `generated_from_pointcloud` | 有可用点云生成 gridmap 工具 | 先执行 gridmap 生成，再 `use_gridmap=true` |
| `unknown` | 最终脚本要求 grid_map，但无来源 | 阻塞 |

`3_move_dir.py` 会复制 `grid_map`，是导航场景的默认 move 脚本。`3_move_dir_no_gridmap.py` 是此前误判产生的绕过脚本，不应进入导航主流程。

当前仓库的 `vla_run_projection_and_trajectory` 应默认使用 `3_move_dir.py`，并在执行前确认 projection 输入下已有 `grid_map`。如果需要 `2_othermethod_cjl_0525.py`，Plan-Agent 必须先确认 Tool capability catalog 中存在该变体；否则记录 `missing_projection_script_variant`。

### 4.4 标定参数

标定参数目录必须作为显式资产检查，不得只按平台名推断。

当前观察到的目录：

```text
NoobScenes/params/20260409_U/sensors
NoobScenes/params/20260529_go2w/sensors
```

Plan-Agent 应检查：

- `sensors` 目录是否存在；
- 是否包含 `fisheye_front.json`；
- 是否包含雷达标定 json；
- `fisheye_front.json` 中 `target` 是否与标准雷达目录一致，例如 `r32_rslidar_points`；
- 用户是否指定了平台或标定版本；
- topic schema 与标定目录是否存在明显冲突。

如果有多个候选标定目录，Plan-Agent 应把候选、推荐项和证据写入 data_profile。若无法确定，应请求用户确认，不得盲选最新目录。

## 5. Plan-Agent 专用检查工具清单

以下工具均为规划阶段只读工具。它们可以读取目录、metadata、脚本和 Tool registry，但不得执行真实数据处理脚本，不得写业务数据。

### 5.1 `vla_inspect_raw_layout`

用途：检查 raw 输入目录结构。

输入：

```json
{
  "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
  "date": "20270605"
}
```

输出重点：

- `raw_date_dir` 是否存在；
- `raw_temp_dir` 是否存在；
- raw segment 列表；
- 每个 segment 是否有 `.db3`；
- 每个 segment 是否有 `metadata.yaml`；
- db3 主文件大小；
- 是否存在 `.db3-shm`、`.db3-wal`。

填充画像字段：

- `dataset.raw_root`
- `dataset.raw_date_dir`
- `dataset.raw_work_dir`
- `raw_segments`
- `processing_state.has_raw_temp`

阻塞条件：

- `raw_date_dir` 不存在；
- selected segment 为空；
- selected segment 缺少 `.db3` 或 `metadata.yaml`。

### 5.2 `vla_inspect_rosbag_metadata`

用途：解析 `metadata.yaml`，必要时 fallback 到 db3 sqlite，获取 ROS bag 元信息。

输出重点：

- rosbag metadata version；
- duration；
- message_count；
- relative db3 files；
- topics_with_message_count；
- 每个 topic 的 name、type、message_count。

填充画像字段：

- `raw_segments.duration_ns`
- `raw_segments.message_count`
- `topics.raw_topics`

阻塞条件：

- metadata 不可解析且 db3 fallback 失败；
- 所有 segment 均无法取得 topic 列表。

### 5.3 `vla_classify_navigation_topic_schema`

用途：根据 topic 事实识别导航 topic schema 与业务角色。

输入来自 `vla_inspect_rosbag_metadata` 的 topic 列表。

输出重点：

- `topic_schema`；
- `topic_mapping_variant`；
- image/lidar/odom/Ins/gridmap 角色识别；
- topic 到 canonical dir 的映射；
- 必要角色是否齐全；
- 缺失角色列表。

填充画像字段：

- `topics.topic_schema`
- `topics.topic_mapping_variant`
- `topics.raw_topics[].role`
- `topics.raw_topics[].canonical_dir`
- `topics.required_roles_present`
- `topics.missing_required_roles`

阻塞条件：

- 缺少前视鱼眼图像；
- 缺少雷达点云；
- odom 与 Ins 都缺失；
- topic 可归为 custom 但没有可用 mapping 配置。

### 5.4 `vla_infer_sync_policy`

用途：推断同步基准和同步输出目录策略。

输入：

- topic schema；
- canonical mapping；
- 各 topic message_count；
- 可用同步脚本能力。

输出重点：

- `sync.query_raw_dir`；
- `sync.query_canonical_dir`；
- `sync.output_dir`；
- `sync.sequence_suffix`；
- 为什么选择该基准。

推荐规则：

- `u_legacy_topics` 通常使用 `lidar_points` 作为 `query_raw_dir`；
- `go2w_current_topics` 通常使用 `rs32_lidar_points` 作为 `query_raw_dir`；
- 如果有 gridmap 且历史流程明确以 gridmap 同步，可选择 `grid_map`；
- 如果候选基准目录不存在或消息数为 0，必须换候选或阻塞。

填充画像字段：

- `sync`
- `stage_variants.extract_and_sync`

### 5.5 `vla_inspect_datatoolbox_variants`

用途：检查 DataToolbox 拆包/同步脚本是否支持数据画像推荐的 topic schema。

输入：

```json
{
  "data_toolbox_src": "/media/heying/hy_data2/GT_dog/modules_ros2/DataToolbox/src",
  "topic_schema": "go2w_current_topics"
}
```

输出重点：

- 拆包脚本候选；
- 同步脚本候选；
- 每个拆包脚本的 TOPIC_WHITELIST；
- 每个同步脚本的 topic_map；
- 是否支持当前 topic schema；
- 当前 ToolSpec 实际会调用哪个脚本。

填充画像字段：

- `stage_variants.extract_and_sync`
- `blocking_issues`
- `warnings`

当前实现风险：

- 本地仓库 `vla_extract_and_sync` 当前固定调用 `1_extract_data_from_bag_multi_process_ros2_U_legacy.py` 和 `2_sync_data_multi_process_U_legacy.py`。
- 如果数据画像为 `go2w_current_topics`，但 Tool capability catalog 没有 current variant，Plan-Agent 必须记录 `missing_extract_sync_variant`，不得生成会误用 legacy 脚本的计划。

### 5.6 `vla_inspect_processing_state`

用途：检查已存在的中间产物，支持恢复、跳过或重处理决策。

检查范围：

- `clip_data/<date>/<segment>/sync_data`；
- `clip_data/<date>/<segment>/tmp_dir`；
- `finish_data/<date>_temp/samples/<date>`；
- `finish_data/<date>`；
- annotation YAML；
- tracking 输出；
- project_npy；
- trajectory json；
- speed_direction json；
- rout_plot_v2；
- final grid_map。

填充画像字段：

- `processing_state`
- `stage_variants` 中可跳过 stage 的 reason/evidence

规则：

- 如果某 stage 被跳过，Plan-Agent 必须在 plan 的 `skipped_stages` 记录原因和 evidence。
- 如果已有产物不完整，不得简单跳过；应标记为 partial，并推荐重跑对应 stage。

### 5.7 `vla_inspect_calibration_assets`

用途：检查 NoobScenes 标定资产。

输入：

```json
{
  "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
  "topic_schema": "go2w_current_topics"
}
```

输出重点：

- `NoobScenes/params/*/sensors` 候选；
- 每个候选是否有 `fisheye_front.json`；
- 每个候选是否有雷达 json；
- `fisheye_front.json.target`；
- 推荐的 `sensor_params_dir`；
- 是否需要用户确认。

填充画像字段：

- `calibration.platform_hint`
- `calibration.sensor_params_dir`
- `calibration.sensor_params_status`
- `stage_variants.prepare_finish_dataset`

阻塞条件：

- 没有任何完整 `sensors` 目录；
- 推荐目录与 canonical 雷达目录冲突；
- 需要用户确认但用户尚未确认。

### 5.8 `vla_infer_localization_policy`

用途：判断定位来源和 NoobScenes 输入构建变体。

输入：

- classified topics；
- scene_mode；
- processing_state；
- 可用脚本。

输出重点：

- `localization.source`；
- `localization.canonical_output`；
- `requires_odom_convert`；
- `requires_cp_ins`；
- 推荐 `build_noobscenes_inputs` 变体。

填充画像字段：

- `localization`
- `stage_variants.build_noobscenes_inputs`

规则：

- raw 为 odom 时，推荐 `odom_convert_resize`。
- raw 为 Ins 时，推荐 `ins_native`，不得执行 odom_convert。
- 室内且需要建图 Ins 时，推荐 `indoor_cp_ins`，并检查 `cp_ins.py` 与建图产物。
- 如果当前 ToolSpec 不支持推荐变体，记录 blocking issue。

### 5.9 `vla_inspect_gridmap_artifacts`

用途：同时检查 raw gridmap topic 和已存在的 grid_map artifact。

输入：

- raw topic 列表；
- clip_root；
- finish_root；
- selected segments。

输出重点：

- raw 是否有 gridmap topic；
- `clip_data/<date>/<segment>/sync_data/<clip>/grid_map` 是否存在；
- `finish_data/<date>_temp/samples/<date>/<clip>/grid_map` 是否存在；
- `finish_data/<date>/<segment>/<clip>/grid_map` 是否存在；
- 可用 gridmap 生成工具是否存在；
- 推荐 `gridmap_source`。

填充画像字段：

- `gridmap.raw_gridmap_topic_present`
- `gridmap.gridmap_source`
- `gridmap.requires_gridmap_processing`
- `gridmap.expect_gridmap_output`
- `stage_variants.gridmap_processing`
- `stage_variants.projection_and_trajectory`
- `stage_variants.validate_outputs`

阻塞条件：

- projection/move/validate 变体要求 grid_map，但 raw、clip artifact 和生成工具都不可用。

### 5.10 `vla_inspect_trajectory_script_variants`

用途：检查轨迹、投影、move 脚本变体。

检查脚本：

```text
2_pt_project/2_othermethod_cjl.py
2_pt_project/2_othermethod_cjl_0525.py
2_pt_project/3_move_dir.py
other_code/cp_gridmap.py
```

输出重点：

- 脚本是否存在；
- `3_move_dir.py` 是否要求 grid_map；
- `2_othermethod_cjl_0525.py` 是否已暴露为 ToolSpec variant；
- `cp_gridmap.py` 的 grid_map 来源策略。

填充画像字段：

- `available_script_variants`
- `stage_variants.projection_and_trajectory`
- `blocking_issues`
- `warnings`

当前实现风险：

- 业务脚本目录存在 `2_othermethod_cjl_0525.py`，但当前 `vla_run_projection_and_trajectory` 固定调用 `2_othermethod_cjl.py`。
- 如果当前服务器流程要求 0525 版本，而 Tool capability catalog 尚未声明该 variant，Plan-Agent 应记录 `missing_projection_script_variant`。

### 5.11 `vla_list_tool_capability_catalog`

用途：返回系统真实可用的工具和变体元数据，防止 Plan-Agent 编造工具。

输出重点：

- tool name；
- scenario；
- stage_kind；
- effects；
- plan_agent_allowed；
- executor_agent_allowed；
- implementation_status；
- variants；
- selectors；
- expected_artifacts；
- recoverable_errors。

规则：

- Plan-Agent 生成 plan 前必须查询此工具。
- 只有 `implementation_status=available` 且 variant status 为 `available` 的工具变体可以进入可执行 plan。
- `planned` 或 `placeholder` 变体只能写入 warnings / blocking_issues / future_work，不得作为 active stage。

### 5.12 `vla_validate_navigation_data_profile`

用途：确定性校验 `NavigationVLADataProfile`。

校验内容：

- 必要字段是否存在；
- 枚举值是否合法；
- evidence 引用是否存在；
- topic_schema 与 topic_mapping_variant 是否一致；
- sync.query_raw_dir 是否能从 raw topic / mapped dir 中解释；
- localization.source 与 build_noobscenes 变体是否一致；
- gridmap 字段与 projection/move/validate 变体是否一致；
- blocking_issues 非空时是否阻止生成可执行 plan；
- warnings 是否带有原因。

输出：

- `ok`；
- `errors`；
- `warnings`；
- `normalized_profile`。

## 6. Stage 变体选择规则

### 6.1 `extract_and_sync`

选择输入：

- `topics.topic_schema`
- `topics.topic_mapping_variant`
- `sync.query_raw_dir`
- `vla_inspect_datatoolbox_variants`
- `vla_list_tool_capability_catalog`

变体规则：

| 条件 | 推荐变体 | 必须检查 |
| --- | --- | --- |
| `u_legacy_topics` | `u_legacy_topics` | legacy 拆包白名单、legacy sync topic_map、query_dir=`lidar_points` |
| `go2w_current_topics` | `go2w_current_topics` | current 拆包白名单、current sync topic_map、query_dir=`rs32_lidar_points` |
| `custom_topics` | `custom_topic_mapping` | 用户或配置提供 mapping，工具支持自定义 topic |
| `unknown_topics` | 无 | 阻塞 |

如果 Tool capability catalog 只支持 legacy，而数据画像为 `go2w_current_topics`，Plan-Agent 必须阻塞或请求新增工具变体。

### 6.2 `prepare_finish_dataset`

选择输入：

- selected segments；
- sync_data 完整性；
- calibration.sensor_params_dir；
- canonical dirs。

变体规则：

| 条件 | 推荐策略 |
| --- | --- |
| 标定目录唯一且完整 | 使用该 `sensor_params_dir` |
| 多个标定目录都可能匹配 | 请求用户确认 |
| 标定目录缺失或 target 冲突 | 阻塞 |

该 stage 不一定需要拆成多个工具，但必须把 sensor params path 显式写入 data_profile 或 stage decision。

### 6.3 `build_noobscenes_inputs`

选择输入：

- `localization.source`
- `localization.requires_odom_convert`
- `localization.requires_cp_ins`
- 可用脚本和 ToolSpec variant。

变体规则：

| 条件 | 推荐变体 |
| --- | --- |
| raw 为 odom | `odom_convert_resize` |
| raw 为原生 Ins | `ins_native` |
| 室内且需要建图 Ins | `indoor_cp_ins` |

当前系统已实现的路径偏向 `odom_convert_resize`。遇到 Ins 或 generated_ins 时，应先确认工具变体可用。

### 6.4 `gridmap_processing`

选择输入：

- raw gridmap topic；
- clip/sync grid_map artifact；
- pointcloud-to-gridmap 工具；
- 用户是否要求 gridmap；
- projection/move/validate 是否要求 gridmap。

变体规则：

| 条件 | 推荐变体 |
| --- | --- |
| clip/sync 已有 grid_map | `cp_gridmap_existing` |
| raw 有 gridmap topic 且拆包同步支持 | `raw_gridmap_topic` |
| 有点云生成 gridmap 工具 | `pointcloud_to_gridmap` |
| 要求 grid_map 但无来源 | 阻塞 |

### 6.5 `projection_and_trajectory`

选择输入：

- gridmap 策略；
- trajectory script variant；
- move script variant；
- Tool capability catalog。

变体规则：

| 条件 | 推荐变体 |
| --- | --- |
| `use_gridmap=true` 且默认轨迹脚本可用 | `cjl_with_gridmap`，move 使用 `3_move_dir.py` |
| 当前服务器要求 0525 轨迹脚本 | `cjl_0525_with_gridmap`，但必须确认 ToolSpec 已支持 |

如果业务脚本存在但 ToolSpec 未暴露，Plan-Agent 不得直接 shell 调用该脚本。

### 6.6 `validate_outputs`

选择输入：

- `gridmap.expect_gridmap_output`
- final output paths；
- active/skipped stages。

变体规则：

| 条件 | 推荐校验 |
| --- | --- |
| `expect_gridmap_output=true` | final outputs 必须包含 `grid_map` |

`vla_validate_outputs` 在导航 full 校验中默认要求 `grid_map`；Plan-Agent 仍应在 data_profile 中明确 `expect_gridmap_output=true`，方便审计。

## 7. 推荐 Plan-Agent 检查顺序

Plan-Agent 应按以下顺序执行规划检查：

1. 调用 `vla_inspect_raw_layout`，确认输入目录、segments、db3、metadata。
2. 调用 `vla_inspect_rosbag_metadata`，获取 topic、duration、message_count。
3. 调用 `vla_classify_navigation_topic_schema`，识别 topic schema、业务角色和 canonical mapping。
4. 如果必要角色缺失，立即记录 blocking issue，并停止生成可执行 plan。
5. 调用 `vla_infer_sync_policy`，确定 query_raw_dir、query_canonical_dir。
6. 调用 `vla_inspect_datatoolbox_variants`，确认拆包/同步脚本和 ToolSpec variant 是否支持该 schema。
7. 调用 `vla_inspect_processing_state`，判断是否已有中间产物以及是否可跳过 stage。
8. 调用 `vla_inspect_calibration_assets`，选择或请求确认 sensors 目录。
9. 调用 `vla_infer_localization_policy`，确定 odom/Ins/indoor cp_ins 策略。
10. 调用 `vla_inspect_gridmap_artifacts`，确定 gridmap_source 和 expect_gridmap_output。
11. 调用 `vla_inspect_trajectory_script_variants`，确认 projection/move/gridmap 脚本变体。
12. 调用 `vla_list_tool_capability_catalog`，确认推荐变体真实可用。
13. 填写 `NavigationVLADataProfile`。
14. 调用 `vla_validate_navigation_data_profile`。
15. 仅当 profile 无 blocking issue 且 required variant 可用时，生成 `VLAWorkflowPlan`。

## 8. blocking issues 与 warnings 规则

必须写入 `blocking_issues` 的情况：

- raw date dir 不存在；
- selected segments 为空；
- segment 缺少 db3 或 metadata；
- 无法解析 topic；
- 缺少前视鱼眼图像、雷达点云、定位来源；
- topic schema 为 custom 但没有 mapping；
- 推荐的拆包/同步变体在 Tool capability catalog 中不存在；
- 标定参数目录缺失或冲突；
- localization 需要的变体不存在；
- 最终要求 grid_map 但没有 raw topic、clip artifact 或生成工具；
- projection/move 变体在 Tool capability catalog 中不存在；
- profile 校验失败。

应写入 `warnings` 的情况：

- db3 存在 `.db3-shm` / `.db3-wal`；
- metadata version 与历史样本不同但字段可解析；
- 有多个标定候选，需要用户确认；
- 发现历史脚本注释与实际调用不一致；
- 已有中间产物但不完整；
- 业务脚本存在，但尚未暴露为 ToolSpec variant；
- 本地路径与服务器默认路径不同，但服务器路径在配置中明确。

## 9. 当前仓库实现状态提示

以下内容用于提醒 Plan-Agent 生成计划时要查询 Tool capability catalog，不得仅凭脚本文件存在就认为可执行：

- 已注册 VLA 工具包括 `vla_check_runtime`、`vla_inspect_raw_date`、`vla_prepare_raw_temp`、`vla_extract_and_sync`、`vla_list_clip_segments`、`vla_prepare_finish_dataset`、`vla_build_noobscenes_inputs`、`vla_run_manual_box_annotation`、`vla_run_tracking`、`vla_run_projection_and_trajectory`、`vla_validate_outputs`。
- `vla_inspect_raw_date` 当前只检查 segment、metadata、db3，不解析 topic。
- `vla_extract_and_sync` 当前代码固定调用 legacy DataToolbox 脚本；go2w/current/custom topic 需要新增或暴露工具变体。
- `vla_build_noobscenes_inputs` 当前固定执行 odom_convert 和 resize；Ins/native/indoor cp_ins 需要新增或暴露工具变体。
- `vla_run_projection_and_trajectory` 当前支持 `use_gridmap`，会切换 move 脚本；但轨迹生成脚本当前固定为 `2_othermethod_cjl.py`。
- 当前服务器业务流使用的 `2_othermethod_cjl_0525.py` 需要作为显式 ToolSpec variant 才能进入可执行 plan。
- 点云生成 gridmap 的工具本地未看到；如果服务器已有，需要复制对应路径和依赖说明后再纳入 Tool capability catalog。

## 10. 对两个历史样本的推荐决策示例

### 10.1 `20270515` 样本

如果检查结果与本文第 3.1 节一致，则推荐：

```json
{
  "topic_schema": "u_legacy_topics",
  "extract_and_sync": "u_legacy_topics",
  "query_raw_dir": "lidar_points",
  "sensor_params_dir": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01/NoobScenes/params/20260409_U/sensors",
  "build_noobscenes_inputs": "odom_convert_resize",
  "gridmap_processing": "cp_gridmap_existing 或 pointcloud_to_gridmap",
  "projection_and_trajectory": "cjl_with_gridmap",
  "validate_outputs": "expect_gridmap"
}
```

前提：

- Tool capability catalog 支持 legacy extract/sync；
- clip/sync 已有 grid_map，或 pointcloud-to-gridmap 工具可用；
- move/validate 变体要求 grid_map 且 grid_map 来源已明确。

### 10.2 `20270605` 样本

如果检查结果与本文第 3.2 节一致，则推荐：

```json
{
  "topic_schema": "go2w_current_topics",
  "extract_and_sync": "go2w_current_topics",
  "query_raw_dir": "rs32_lidar_points",
  "sensor_params_dir": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01/NoobScenes/params/20260529_go2w/sensors",
  "build_noobscenes_inputs": "odom_convert_resize",
  "gridmap_processing": "cp_gridmap_existing 或 pointcloud_to_gridmap",
  "projection_and_trajectory": "cjl_0525_with_gridmap",
  "validate_outputs": "expect_gridmap"
}
```

前提：

- Tool capability catalog 支持 go2w/current extract/sync；
- clip/sync 已有 grid_map，或 pointcloud-to-gridmap 工具可用；
- Tool capability catalog 支持 `2_othermethod_cjl_0525.py` 对应 projection variant；
- move/validate 变体要求 grid_map 且 grid_map 来源已明确。

如果上述前提不满足，Plan-Agent 必须生成阻塞问题，而不是降级为旧脚本静默执行。

## 11. 需要从服务器补充的材料

当前本地材料还不足以把以下能力写成可执行 available 变体：

- 从点云生成 gridmap 的工具代码、入口命令、依赖环境和输入输出约定；
- 当前服务器是否已有支持 `go2w_current_topics` 的 agent ToolSpec 版本；
- `2_othermethod_cjl_0525.py` 相比 `2_othermethod_cjl.py` 的业务差异说明；
- 如果山猫/Ins 数据仍需支持，需要补充一份包含 `/drivers/ins/Ins` 的 raw metadata 样本和对应 run_Ins/run_odom 差异。

在这些材料补齐前，Plan-Agent 可以在 Markdown 中理解这些变体，但只有 Tool capability catalog 标记为 `available` 的变体可以进入 active stages。
