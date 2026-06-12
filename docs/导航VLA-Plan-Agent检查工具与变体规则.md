# 导航 VLA Plan-Agent 检查工具与变体规则

## 1. 文档目的

本文档是 Plan-Agent 的规划操作手册。

Plan-Agent 必须先读取检查工具返回的 `observations`，再生成规划草稿。不得按日期、目录名或历史样本名硬编码流程。

日期只能作为样本标签、目录键、日志字段或 evidence 引用。流程判断必须来自：

- raw 目录、segment、db3、metadata 是否存在。
- ROS topic 的 name、type、message_count、duration。
- image、lidar、odom、Ins、gridmap 等业务角色是否齐全。
- topic 到 canonical dir 的映射是否明确。
- clip/sync/finish 中间产物是否存在且完整。
- 标定参数目录是否存在且匹配。
- Tool capability catalog 中工具和变体是否真实可用。

历史样本只能作为规则设计参考，不能作为 Plan-Agent 的判定条件。

## 2. Plan-Agent 输出与校验闭环

Plan-Agent 的直接产物是草稿，不是最终可信 artifact：

- `NavigationVLADataProfile` 草稿。
- `VLAWorkflowPlan` 草稿。

草稿必须经过确定性校验：

1. 生成 `NavigationVLADataProfile` 草稿。
2. 调用 `vla_validate_navigation_data_profile`。
3. 若校验失败，根据 validation feedback 修复草稿并重试。
4. 仅当 profile 无 blocking issue，且必需工具变体可用时，生成 `VLAWorkflowPlan` 草稿。
5. 再执行 plan schema 校验和语义校验。
6. 若 plan 校验失败，根据 validation feedback 修复并重试。

禁止把未校验草稿当作正式 `data_profile.json` 或 `plan.json`。

## 3. 必须调用或参考的检查工具

规划阶段工具只读。不得执行真实数据处理脚本，不得写业务数据。

推荐顺序：

1. `vla_inspect_raw_layout`
   - 检查 raw 根目录、日期目录、segments、db3、metadata。
   - 缺少 raw date dir、selected segments、db3 或 metadata 时阻塞。

2. `vla_inspect_rosbag_metadata`
   - 解析 `metadata.yaml`，必要时 fallback 到 db3 sqlite。
   - 返回 topic、type、message_count、duration。
   - 无法取得 topic 列表时阻塞。

3. `vla_classify_navigation_topic_schema`
   - 根据 topic 事实识别 schema、业务角色、canonical mapping。
   - 缺少前视鱼眼图像、雷达点云、定位来源时阻塞。

4. `vla_infer_sync_policy`
   - 推断 `sync.query_raw_dir`、`sync.query_canonical_dir`、输出目录。
   - 候选同步基准不存在或 message_count 为 0 时换候选或阻塞。

5. `vla_inspect_datatoolbox_variants`
   - 检查拆包/同步脚本是否支持当前 topic schema。
   - ToolSpec 未暴露所需变体时记录 blocking issue。

6. `vla_inspect_processing_state`
   - 检查 clip/sync/finish/annotation/tracking/projection/grid_map 等中间产物。
   - 完整产物可用于跳过 stage。
   - 不完整产物标记 partial，并建议重跑相关 stage。

7. `vla_inspect_calibration_assets`
   - 检查 `NoobScenes/params/*/sensors`。
   - 确认 `fisheye_front.json`、雷达 json、`target` 与 canonical lidar dir。
   - 多个候选无法确定时请求用户确认，不得盲选最新目录。

8. `vla_infer_localization_policy`
   - 判断 `odom`、`ins`、`generated_ins` 或 `unknown`。
   - 推荐 `build_noobscenes_inputs` 变体。

9. `vla_inspect_gridmap_artifacts`
   - 检查 raw gridmap topic、clip/sync `grid_map`、finish/temp `grid_map`。
   - 本工具只返回文件事实，不判断 pointcloud-to-gridmap 工具是否可用。

10. `vla_inspect_trajectory_script_variants`
    - 检查 projection、trajectory、move、cp_gridmap 脚本变体。
    - 脚本存在但 ToolSpec 未暴露时，只能进入 warning 或 blocking issue。

11. `vla_list_tool_capability_catalog`
    - 规划前必须调用。
    - 以 catalog 为工具可执行性的唯一准绳。

12. `vla_validate_navigation_data_profile`
    - 校验 profile schema、枚举值、evidence、语义一致性。

## 4. 决策规则

### 4.1 Topic Schema

Topic schema 由 topic 组合决定，不由日期决定。

| schema | 必要事实 | canonical mapping | 常见同步基准 |
| --- | --- | --- | --- |
| `u_legacy_topics` | `/cam_video5/csi_cam/image_raw/compressed` + `/lidar_points` + `/utlidar/robot_odom_systime` | `cam_video5 -> fisheye_front`；`lidar_points -> r32_rslidar_points`；`utlidar -> odom` | `lidar_points` |
| `go2w_current_topics` | `/cam_video4/csi_cam/image_raw/compressed` + `/rs32_lidar_points` + `/sport_odom` | `cam_video4 -> fisheye_front`；`rs32_lidar_points -> r32_rslidar_points`；`sport_odom -> odom` | `rs32_lidar_points` |
| `shanmao_ins_topics` | 前视鱼眼 + 雷达 + `/drivers/ins/Ins` | 由检查工具确认 | 雷达或 gridmap |
| `custom_topics` | 必要业务角色齐全，但 topic 名不匹配已知 schema | 必须由用户或配置提供 | 由检查工具推断 |
| `unknown_topics` | 必要角色缺失或无法映射 | 无 | 阻塞 |

规则：

- `custom_topics` 没有 mapping 时阻塞。
- `unknown_topics` 阻塞。
- 必要角色缺失时，不得生成可执行 plan。

### 4.2 Sync Policy

同步基准必须来自 observations：

- `u_legacy_topics` 通常使用 `lidar_points`。
- `go2w_current_topics` 通常使用 `rs32_lidar_points`。
- 若 raw 或中间产物存在可用 gridmap，且流程明确以 gridmap 同步，可选择 `grid_map`。
- 同步基准必须能映射到 canonical dir。
- 同步基准 topic 的 message_count 必须大于 0。

`VLAWorkflowPlan` 中只写 stage、tool、variant、effects、decision_ref、status 等计划信息。不要写具体工具参数。

### 4.3 Localization

| `localization.source` | 条件 | 规则 |
| --- | --- | --- |
| `odom` | raw topic 包含 Odometry，例如 `/utlidar/robot_odom_systime` 或 `/sport_odom` | 使用 `odom_convert_resize`，需要 odom convert |
| `ins` | raw topic 包含 `/drivers/ins/Ins`，且下游按 Ins 读取 | 使用 `ins_native`，不得执行 odom convert |
| `generated_ins` | 室内或特定平台需要从建图结果复制 Ins | 使用 `indoor_cp_ins`，必须检查 `cp_ins.py` 和建图产物 |
| `unknown` | 无 odom/Ins 或无法判断 | 阻塞 |

如果推荐 localization 变体在 Tool capability catalog 中不可用，记录 `missing_localization_variant`。

### 4.4 Calibration

标定目录必须显式检查：

- `sensors` 目录存在。
- 包含 `fisheye_front.json`。
- 包含雷达标定 json。
- `fisheye_front.json.target` 与 canonical lidar dir 一致，例如 `r32_rslidar_points`。
- topic schema 与标定目录无明显冲突。

多个候选都可能匹配时：

- 写入候选、推荐项和 evidence。
- 若无法确定，阻塞并请求用户确认。

### 4.5 Gridmap

导航最终输出默认需要 `grid_map`。不得因为 raw 中没有 gridmap topic 就认为最终不需要 gridmap。

如果 raw 没有 gridmap topic，必须按顺序检查：

1. clip/sync 是否已有 `grid_map`。
2. Tool capability catalog 是否有可用的 `vla_prepare_gridmap/pointcloud_to_gridmap`。
3. 两者都没有时，记录 `missing_gridmap_source_or_generator`。

合法来源：

| `gridmap.gridmap_source` | 条件 | 规则 |
| --- | --- | --- |
| `raw_topic` | raw 有 gridmap topic，且拆包/同步变体支持 | 同步 gridmap，后续可进入 projection/validate |
| `existing_gridmap_artifact` | clip/sync 已有 `grid_map` | 使用 copy/convert 语义，后续可进入 projection/validate |
| `generated_from_pointcloud` | pointcloud-to-gridmap 工具可用 | 先执行 `gridmap_processing`，后续可进入 projection/validate |
| `unknown` | 无来源且无生成工具 | 阻塞 |

当点云生成 gridmap 工具可用时，必须设置：

```json
{
  "gridmap": {
    "gridmap_source": "generated_from_pointcloud"
  },
  "stage_variants": {
    "gridmap_processing": {
      "variant": "pointcloud_to_gridmap"
    }
  }
}
```

同时：

- `gridmap_processing` 必须进入 active stages。
- `projection_and_trajectory` 只能在已有 `grid_map` 或可生成 `grid_map` 时进入可执行计划。
- `validate_outputs` 只能在已有 `grid_map` 或可生成 `grid_map` 时进入可执行计划。

### 4.6 Projection And Trajectory

默认规则：

- 导航主流程使用带 gridmap 的 projection/move。
- `3_move_dir.py` 要求复制 `grid_map`。
- `3_move_dir_no_gridmap.py` 不应进入导航主流程。

变体规则：

- `cjl_with_gridmap`：默认轨迹脚本可用，且 `grid_map` 来源明确。
- `cjl_0525_with_gridmap`：仅当 Tool capability catalog 声明该 variant 为 `available` 时可用。

业务脚本存在但 ToolSpec 未暴露时，不得直接 shell 调用。

### 4.7 Validate Outputs

导航 full 校验默认要求最终输出包含 `grid_map`。

Plan-Agent 必须显式设置：

```json
{
  "gridmap": {
    "expect_gridmap_output": true
  }
}
```

若无法保证最终 `grid_map`，`validate_outputs` 不得进入 active stages。

## 5. Tool Capability Catalog 使用规则

Plan-Agent 必须以 `vla_list_tool_capability_catalog` 为可执行能力来源。

active stages 只允许使用同时满足以下条件的工具变体：

- tool 的 `implementation_status = "available"`。
- variant 的 `status = "available"`。
- `plan_agent_allowed = true`。
- stage_kind、effects 与当前决策一致。

`stage_variants.*.status` 只能使用以下枚举：

- `available`
- `planned`
- `placeholder`
- `deprecated`

禁止写入其它 status。阻塞原因写入 `blocking_issues`，不要塞进 status 字段。

以下变体不得进入 active stages：

- `planned`
- `placeholder`
- `deprecated`
- catalog 中不存在的变体
- 脚本存在但 ToolSpec 未暴露的变体

这些内容只能写入：

- `warnings`
- `blocking_issues`
- `future_work`

如果本文档与 Tool capability catalog 冲突，以 catalog 为准。Plan-Agent 不得编造工具、变体或执行路径。

## 6. 阻塞条件与 Warnings

### 6.1 Blocking Issues

以下情况必须写入 `blocking_issues`：

- raw date dir 不存在。
- selected segments 为空。
- segment 缺少 db3 或 metadata。
- metadata 与 db3 fallback 都无法解析 topic。
- 缺少前视鱼眼图像、雷达点云或定位来源。
- topic schema 为 `custom_topics` 但没有 mapping。
- 推荐拆包/同步变体不在 Tool capability catalog 中，或不是 `available`。
- 标定参数目录缺失、冲突，或需要用户确认但尚未确认。
- localization 所需变体不可用。
- 最终要求 `grid_map`，但没有 raw topic、clip/sync artifact、pointcloud-to-gridmap 生成工具。
- projection/move 所需变体不可用。
- `NavigationVLADataProfile` 校验失败。
- `VLAWorkflowPlan` 校验失败。

推荐 issue code：

- `missing_raw_date_dir`
- `missing_selected_segments`
- `missing_rosbag_metadata_or_db3`
- `missing_required_navigation_topics`
- `missing_topic_mapping`
- `missing_extract_sync_variant`
- `missing_calibration_assets`
- `missing_localization_variant`
- `missing_gridmap_source_or_generator`
- `missing_projection_script_variant`
- `profile_validation_failed`
- `plan_validation_failed`

### 6.2 Warnings

以下情况写入 `warnings`：

- db3 旁存在 `.db3-shm` 或 `.db3-wal`。
- metadata version 与历史样本不同，但字段可解析。
- 有多个标定候选。
- 历史脚本注释与实际调用不一致。
- 已有中间产物但不完整。
- 业务脚本存在，但 ToolSpec 未暴露为 variant。
- 本地路径与服务器默认路径不同，但配置中已有服务器路径。
- catalog 中存在 `planned`、`placeholder` 或 `deprecated` 变体可作为未来工作参考。

## 7. 最终 JSON 输出要求

Plan-Agent 最终输出必须是严格 JSON：

- 不要 Markdown。
- 不要解释文字。
- 不要代码块围栏。
- 不要 `{...}`、`[...]`、`TODO`、`TBD` 或占位符。
- 所有字符串、数组、对象必须完整可解析。
- 枚举值必须合法。
- evidence 引用必须指向已存在的 observations 或 validation feedback。

`VLAWorkflowPlan` 中不要写具体工具参数。只写计划层信息，例如：

- `stage`
- `tool`
- `variant`
- `effects`
- `decision_ref`
- `status`
- `depends_on`
- `produces`
- `skipped_reason`

如果存在 blocking issue：

- 可以输出 profile 草稿和阻塞说明。
- 不得输出包含不可执行 active stages 的 plan。

## 8. 极简决策示例

示例只说明 observations 到决策的映射。不得按样本日期硬编码。

### 8.1 Legacy Topic 组合

当 observations 显示：

- topic 包含 `/cam_video5/csi_cam/image_raw/compressed`。
- topic 包含 `/lidar_points`。
- topic 包含 `/utlidar/robot_odom_systime`。
- raw 无 gridmap topic。
- catalog 中 legacy extract/sync 为 `available`。

推荐决策：

```json
{
  "topic_schema": "u_legacy_topics",
  "topic_mapping_variant": "cam5_lidar_points_utlidar_odom",
  "sync": {
    "query_raw_dir": "lidar_points",
    "query_canonical_dir": "r32_rslidar_points"
  },
  "localization": {
    "source": "odom",
    "requires_odom_convert": true
  },
  "stage_variants": {
    "extract_and_sync": {
      "variant": "u_legacy_topics",
      "status": "available"
    },
    "build_noobscenes_inputs": {
      "variant": "odom_convert_resize",
      "status": "available"
    }
  }
}
```

若 clip/sync 有 `grid_map`，使用 `existing_gridmap_artifact`。若没有，但 `pointcloud_to_gridmap` available，使用 `generated_from_pointcloud` 并激活 `gridmap_processing`。两者都没有时，记录 `missing_gridmap_source_or_generator`。

### 8.2 Go2w Current Topic 组合

当 observations 显示：

- topic 包含 `/cam_video4/csi_cam/image_raw/compressed`。
- topic 包含 `/rs32_lidar_points`。
- topic 包含 `/sport_odom`。
- raw 无 gridmap topic。
- catalog 中 go2w/current extract/sync 为 `available`。

推荐决策：

```json
{
  "topic_schema": "go2w_current_topics",
  "topic_mapping_variant": "cam4_rs32_sport_odom",
  "sync": {
    "query_raw_dir": "rs32_lidar_points",
    "query_canonical_dir": "r32_rslidar_points"
  },
  "localization": {
    "source": "odom",
    "requires_odom_convert": true
  },
  "stage_variants": {
    "extract_and_sync": {
      "variant": "go2w_current_topics",
      "status": "available"
    },
    "build_noobscenes_inputs": {
      "variant": "odom_convert_resize",
      "status": "available"
    }
  }
}
```

若流程需要 `cjl_0525_with_gridmap`，必须先确认 catalog 中该 projection variant 为 `available`。否则记录 `missing_projection_script_variant`，不得静默降级到旧脚本。
