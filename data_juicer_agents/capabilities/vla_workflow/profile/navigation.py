from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TopicSchema = Literal[
    "u_legacy_topics",
    "go2w_current_topics",
    "shanmao_ins_topics",
    "custom_topics",
    "unknown_topics",
]
LocalizationSource = Literal["odom", "ins", "generated_ins", "unknown"]
GridmapSource = Literal[
    "raw_topic",
    "existing_gridmap_artifact",
    "generated_from_pointcloud",
    "unknown",
]
VariantStatus = Literal["available", "planned", "placeholder", "deprecated"]


class ProfileIssue(BaseModel):
    type: str
    message: str = ""
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class StageVariantDecision(BaseModel):
    variant: str
    status: VariantStatus = "available"
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)


class NavigationDatasetProfile(BaseModel):
    date: str
    raw_root: str
    raw_date_dir: str
    raw_work_dir: str
    clip_root: str
    finish_root: str
    trajectory_root: str
    scene_mode: Literal["in", "out", "unknown"] = "unknown"
    selected_segments: list[str] = Field(default_factory=list)


class RawSegmentProfile(BaseModel):
    name: str
    path: str
    has_db3: bool = False
    has_metadata_yaml: bool = False
    db3_files: list[str] = Field(default_factory=list)
    duration_ns: int | None = None
    message_count: int | None = None


class RawTopicProfile(BaseModel):
    name: str
    type: str = ""
    role: str = ""
    canonical_dir: str = ""
    message_count: int | None = None


class NavigationTopicsProfile(BaseModel):
    source_type: Literal["ros2_db3"] = "ros2_db3"
    raw_topics: list[RawTopicProfile] = Field(default_factory=list)
    topic_schema: TopicSchema
    topic_mapping_variant: str = ""
    required_roles_present: bool = False
    missing_required_roles: list[str] = Field(default_factory=list)


class NavigationSyncProfile(BaseModel):
    query_raw_dir: str
    query_canonical_dir: str
    output_dir: str = "sync_data"
    sequence_suffix: str = "zhigu_wuhan"


class NavigationProcessingState(BaseModel):
    has_raw_temp: bool = False
    has_sync_data: bool = False
    sync_data_segments: list[str] = Field(default_factory=list)
    has_finish_temp_samples: bool = False
    has_annotation_yaml: bool = False
    has_tracking_outputs: bool = False
    has_project_npy: bool = False
    has_final_outputs: bool = False
    has_final_grid_map: bool = False


class NavigationLocalizationProfile(BaseModel):
    source: LocalizationSource
    canonical_output: str = ""
    requires_odom_convert: bool = False
    requires_cp_ins: bool = False


class NavigationCalibrationProfile(BaseModel):
    platform_hint: str = ""
    sensor_params_dir: str = ""
    sensor_params_status: Literal["present", "missing", "incomplete", "unknown"] = (
        "unknown"
    )


class NavigationGridmapProfile(BaseModel):
    raw_gridmap_topic_present: bool = False
    gridmap_source: GridmapSource
    requires_gridmap_processing: bool = False
    expect_gridmap_output: bool = True
    available_gridmap_artifacts: list[str] = Field(default_factory=list)
    artifact_locations: list[str] = Field(default_factory=list)
    projection_input_gridmap_ready: bool = False
    reason: str = ""


class NavigationVLADataProfile(BaseModel):
    schema_version: int = 1
    scenario: Literal["navigation_vla"] = "navigation_vla"
    dataset: NavigationDatasetProfile
    raw_segments: list[RawSegmentProfile] = Field(default_factory=list)
    topics: NavigationTopicsProfile
    sync: NavigationSyncProfile
    processing_state: NavigationProcessingState
    localization: NavigationLocalizationProfile
    calibration: NavigationCalibrationProfile
    gridmap: NavigationGridmapProfile
    stage_variants: dict[str, StageVariantDecision] = Field(default_factory=dict)
    blocking_issues: list[ProfileIssue] = Field(default_factory=list)
    warnings: list[ProfileIssue] = Field(default_factory=list)
    evidence: dict[str, list[str]] = Field(default_factory=dict)

