from __future__ import annotations
import re
import uuid
import datetime
from typing import Any
from .step import Workflow, WorkflowStep, DataSource, StepStatus


# ---------------------------------------------------------------------------
# Intent patterns → tool chains
# Each entry: (regex, builder_fn)  builder receives (data_sources, goal, ws)
# ---------------------------------------------------------------------------

def _make_id() -> str:
    return f"wf_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"


def _ds(name: str) -> str:
    return f"${{data_sources.{name}}}"


def _ws(filename: str) -> str:
    return f"${{workspace}}/{filename}"


# ---- template builders -----------------------------------------------

def _build_buffer_analysis(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    inp = sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="缓冲区分析",
            tool="arcpy.analysis.Buffer",
            description="对输入要素创建缓冲区",
            params={
                "in_features": _ds(inp),
                "out_feature_class": _ws("buffer_output.shp"),
                "buffer_distance_or_field": "1000 Meters",
                "dissolve_option": "NONE",
            },
            editable_params=["buffer_distance_or_field", "out_feature_class", "dissolve_option"],
            outputs=["buffer_output"],
            estimated_duration="10s",
        ),
        WorkflowStep(
            step_id=2,
            name="添加到地图",
            tool="arcpy.mp.AddLayerToMap",
            description="将结果图层加载到当前地图",
            params={"layer_path": _ws("buffer_output.shp")},
            editable_params=[],
            depends_on=[1],
            estimated_duration="2s",
        ),
    ]


def _build_spatial_join(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    target = sources[0].name
    join = sources[1].name if len(sources) > 1 else sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="空间连接",
            tool="arcpy.analysis.SpatialJoin",
            description="将属性从连接要素转移到目标要素",
            params={
                "target_features": _ds(target),
                "join_features": _ds(join),
                "out_feature_class": _ws("spatial_join.shp"),
                "join_operation": "JOIN_ONE_TO_ONE",
                "join_type": "KEEP_ALL",
                "match_option": "INTERSECT",
            },
            editable_params=["join_operation", "join_type", "match_option", "out_feature_class"],
            outputs=["spatial_join"],
            estimated_duration="20s",
        ),
    ]


def _build_density_analysis(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    inp = sources[0].name
    steps = [
        WorkflowStep(
            step_id=1,
            name="核密度分析",
            tool="arcpy.sa.KernelDensity",
            description="计算点要素或折线要素的核密度",
            params={
                "in_features": _ds(inp),
                "population_field": "NONE",
                "out_raster": _ws("kernel_density.tif"),
                "cell_size": 100,
                "search_radius": 1000,
                "area_unit_scale_factor": "SQUARE_KILOMETERS",
            },
            editable_params=["cell_size", "search_radius", "population_field", "area_unit_scale_factor"],
            outputs=["kernel_density"],
            estimated_duration="30s",
        ),
        WorkflowStep(
            step_id=2,
            name="重分类",
            tool="arcpy.sa.Reclassify",
            description="将核密度结果重分类为等级",
            params={
                "in_raster": _ws("kernel_density.tif"),
                "reclass_field": "Value",
                "remap": "0 1000 1;1000 3000 2;3000 5000 3;5000 10000 4;10000 99999 5",
                "out_raster": _ws("density_class.tif"),
            },
            editable_params=["remap", "out_raster"],
            depends_on=[1],
            outputs=["density_class"],
            estimated_duration="10s",
        ),
        WorkflowStep(
            step_id=3,
            name="应用符号化",
            tool="arcpy.mp.ApplySymbologyFromLayer",
            description="为分类栅格应用渐变色彩符号",
            params={
                "in_layer": _ws("density_class.tif"),
                "symbology_type": "GRADUATED_COLORS",
            },
            editable_params=["symbology_type"],
            depends_on=[2],
            estimated_duration="5s",
        ),
    ]
    return steps


def _build_hot_spot(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    inp = sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="热点分析 (Getis-Ord Gi*)",
            tool="arcpy.stats.HotSpots",
            description="识别具有统计显著性的高值（热点）和低值（冷点）聚类",
            params={
                "Input_Feature_Class": _ds(inp),
                "Input_Field": "VALUE",
                "Output_Feature_Class": _ws("hotspot.shp"),
                "Conceptualization_of_Spatial_Relationships": "FIXED_DISTANCE_BAND",
                "Distance_Method": "EUCLIDEAN_DISTANCE",
                "Standardization": "ROW",
                "Distance_Band_or_Threshold_Distance": 0,
            },
            editable_params=["Input_Field", "Conceptualization_of_Spatial_Relationships", "Distance_Band_or_Threshold_Distance"],
            outputs=["hotspot"],
            estimated_duration="60s",
        ),
    ]


def _build_clip_raster(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    raster = next((s for s in sources if s.type == "raster"), sources[0])
    boundary = next((s for s in sources if s.type == "vector"), None)
    params: dict[str, Any] = {
        "in_raster": _ds(raster.name),
        "rectangle": "#",
        "out_raster": _ws("clipped.tif"),
    }
    if boundary:
        params["in_template_dataset"] = _ds(boundary.name)
        params["clipping_geometry"] = "ClippingGeometry"
    return [
        WorkflowStep(
            step_id=1,
            name="裁剪栅格",
            tool="arcpy.management.Clip",
            description="按矢量边界裁剪栅格影像",
            params=params,
            editable_params=["out_raster", "clipping_geometry"],
            outputs=["clipped"],
            estimated_duration="20s",
        ),
    ]


def _build_slope_aspect(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    dem = sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="坡度分析",
            tool="arcpy.sa.Slope",
            description="从 DEM 计算地面坡度",
            params={
                "in_raster": _ds(dem),
                "output_measurement": "DEGREE",
                "z_factor": 1,
                "out_raster": _ws("slope.tif"),
            },
            editable_params=["output_measurement", "z_factor"],
            outputs=["slope"],
            estimated_duration="15s",
        ),
        WorkflowStep(
            step_id=2,
            name="坡向分析",
            tool="arcpy.sa.Aspect",
            description="从 DEM 计算坡向",
            params={
                "in_raster": _ds(dem),
                "out_raster": _ws("aspect.tif"),
            },
            editable_params=[],
            outputs=["aspect"],
            estimated_duration="15s",
        ),
        WorkflowStep(
            step_id=3,
            name="山体阴影",
            tool="arcpy.sa.HillShade",
            description="生成山体阴影图提升可视化效果",
            params={
                "in_raster": _ds(dem),
                "azimuth": 315,
                "altitude": 45,
                "model_shadows": "NO_SHADOWS",
                "z_factor": 1,
                "out_raster": _ws("hillshade.tif"),
            },
            editable_params=["azimuth", "altitude", "z_factor"],
            outputs=["hillshade"],
            estimated_duration="15s",
        ),
    ]


def _build_network_route(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    network = next((s for s in sources if s.type == "network"), sources[0])
    stops = next((s for s in sources if s.type == "vector" and s != network), None)
    return [
        WorkflowStep(
            step_id=1,
            name="创建路径分析图层",
            tool="arcpy.na.MakeRouteAnalysisLayer",
            description="创建网络分析路径图层",
            params={
                "network_data_source": _ds(network.name),
                "layer_name": "Route",
                "travel_mode": "Driving Time",
                "time_of_day": None,
            },
            editable_params=["travel_mode", "time_of_day"],
            outputs=["route_layer"],
            estimated_duration="5s",
        ),
        WorkflowStep(
            step_id=2,
            name="添加途经点",
            tool="arcpy.na.AddLocations",
            description="将停靠点要素添加到路径分析图层",
            params={
                "in_network_analysis_layer": "${outputs.route_layer}",
                "sub_layer": "Stops",
                "in_table": _ds(stops.name) if stops else "",
                "field_mappings": "",
                "search_tolerance": "5000 Meters",
            },
            editable_params=["search_tolerance", "in_table"],
            depends_on=[1],
            estimated_duration="10s",
        ),
        WorkflowStep(
            step_id=3,
            name="执行路径求解",
            tool="arcpy.na.Solve",
            description="计算最优路径",
            params={
                "in_network_analysis_layer": "${outputs.route_layer}",
                "ignore_invalids": "SKIP",
                "terminate_on_solve_error": "TERMINATE",
            },
            editable_params=["ignore_invalids"],
            depends_on=[2],
            outputs=["solved_route"],
            estimated_duration="30s",
        ),
    ]


def _build_service_area(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    network = next((s for s in sources if s.type == "network"), sources[0])
    facilities = next((s for s in sources if s.type == "vector"), None)
    return [
        WorkflowStep(
            step_id=1,
            name="创建服务区分析图层",
            tool="arcpy.na.MakeServiceAreaAnalysisLayer",
            description="创建基于时间或距离的服务区分析图层",
            params={
                "network_data_source": _ds(network.name),
                "layer_name": "ServiceArea",
                "travel_mode": "Driving Time",
                "travel_direction": "FROM_FACILITIES",
                "cutoffs": [5, 10, 15],
                "geometry_at_cutoff": "RINGS",
            },
            editable_params=["travel_mode", "cutoffs", "travel_direction", "geometry_at_cutoff"],
            outputs=["sa_layer"],
            estimated_duration="5s",
        ),
        WorkflowStep(
            step_id=2,
            name="添加设施点",
            tool="arcpy.na.AddLocations",
            description="添加服务设施点",
            params={
                "in_network_analysis_layer": "${outputs.sa_layer}",
                "sub_layer": "Facilities",
                "in_table": _ds(facilities.name) if facilities else "",
                "search_tolerance": "5000 Meters",
            },
            editable_params=["search_tolerance", "in_table"],
            depends_on=[1],
            estimated_duration="5s",
        ),
        WorkflowStep(
            step_id=3,
            name="求解服务区",
            tool="arcpy.na.Solve",
            description="计算服务区多边形",
            params={
                "in_network_analysis_layer": "${outputs.sa_layer}",
                "ignore_invalids": "SKIP",
            },
            editable_params=[],
            depends_on=[2],
            outputs=["service_area_polys"],
            estimated_duration="60s",
        ),
    ]


def _build_ndvi(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    raster = sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="计算 NDVI",
            tool="arcpy.sa.RasterCalculator",
            description="使用近红外和红波段计算植被指数 NDVI = (NIR - Red) / (NIR + Red)",
            params={
                "expression": '(Float("${data_sources.' + raster + '}\\\\Band_5") - Float("${data_sources.' + raster + '}\\\\Band_4")) / (Float("${data_sources.' + raster + '}\\\\Band_5") + Float("${data_sources.' + raster + '}\\\\Band_4"))',
                "output_raster": _ws("ndvi.tif"),
            },
            editable_params=["expression", "output_raster"],
            outputs=["ndvi"],
            estimated_duration="30s",
        ),
        WorkflowStep(
            step_id=2,
            name="NDVI 重分类",
            tool="arcpy.sa.Reclassify",
            description="将 NDVI 重分类为植被覆盖等级",
            params={
                "in_raster": _ws("ndvi.tif"),
                "reclass_field": "Value",
                "remap": "-1 0 1;0 0.2 2;0.2 0.4 3;0.4 0.6 4;0.6 1 5",
                "out_raster": _ws("ndvi_class.tif"),
            },
            editable_params=["remap"],
            depends_on=[1],
            outputs=["ndvi_class"],
            estimated_duration="10s",
        ),
    ]


def _build_population_density(sources: list[DataSource], goal: str, ws: str) -> list[WorkflowStep]:
    poly = sources[0].name
    pop_src = sources[1].name if len(sources) > 1 else sources[0].name
    return [
        WorkflowStep(
            step_id=1,
            name="空间连接（关联人口数据）",
            tool="arcpy.analysis.SpatialJoin",
            description="将人口数据与行政区划面要素连接",
            params={
                "target_features": _ds(poly),
                "join_features": _ds(pop_src),
                "out_feature_class": _ws("pop_joined.shp"),
                "join_operation": "JOIN_ONE_TO_ONE",
                "match_option": "CONTAINS",
            },
            editable_params=["match_option"],
            outputs=["pop_joined"],
            estimated_duration="20s",
        ),
        WorkflowStep(
            step_id=2,
            name="计算人口密度字段",
            tool="arcpy.management.CalculateField",
            description="面积单位换算后计算人口密度（人/km²）",
            params={
                "in_table": _ws("pop_joined.shp"),
                "field": "POP_DENSITY",
                "expression": "!POP_COUNT! / (!Shape_Area! / 1000000)",
                "expression_type": "PYTHON3",
                "field_type": "DOUBLE",
            },
            editable_params=["field", "expression"],
            depends_on=[1],
            estimated_duration="5s",
        ),
        WorkflowStep(
            step_id=3,
            name="选择高密度区域",
            tool="arcpy.management.SelectLayerByAttribute",
            description="选出人口密度超过阈值的区域",
            params={
                "in_layer_or_view": _ws("pop_joined.shp"),
                "selection_type": "NEW_SELECTION",
                "where_clause": "POP_DENSITY > 5000",
            },
            editable_params=["where_clause"],
            depends_on=[2],
            estimated_duration="3s",
        ),
        WorkflowStep(
            step_id=4,
            name="应用分级色彩符号",
            tool="arcpy.mp.ApplySymbologyFromLayer",
            description="按人口密度分级渲染",
            params={
                "in_layer": _ws("pop_joined.shp"),
                "symbology_type": "GRADUATED_COLORS",
                "symbology_field": "POP_DENSITY",
            },
            editable_params=["symbology_type", "symbology_field"],
            depends_on=[2],
            estimated_duration="5s",
        ),
    ]


# ---- intent matcher --------------------------------------------------

_INTENT_RULES: list[tuple[list[str], Any]] = [
    (["缓冲", "buffer", "缓冲区"], _build_buffer_analysis),
    (["空间连接", "spatial join", "属性连接"], _build_spatial_join),
    (["热点", "hotspot", "冷点", "getis", "gi*", "聚类分析"], _build_hot_spot),
    (["核密度", "密度分析", "kernel density", "密度图"], _build_density_analysis),
    (["裁剪", "clip", "掩膜", "mask"], _build_clip_raster),
    (["坡度", "坡向", "dem", "地形", "山体阴影", "slope", "aspect"], _build_slope_aspect),
    (["路径", "route", "最短路", "导航", "routing"], _build_network_route),
    (["服务区", "service area", "等时圈", "可达性"], _build_service_area),
    (["ndvi", "植被", "绿化", "遥感植被"], _build_ndvi),
    (["人口密度", "人口分布", "density"], _build_population_density),
]


class WorkflowPlanner:
    def plan(
        self,
        goal: str,
        data_sources: list[dict],
        output_workspace: str = "",
        custom_steps: list[dict] | None = None,
    ) -> dict:
        sources = [DataSource(**ds) for ds in data_sources]
        # 如果没有数据源，添加占位符让用户后续在参数编辑器中指定
        if not sources:
            sources = [DataSource(name="输入数据", path="<请指定数据路径>", type="vector")]

        if custom_steps:
            # AI 提供了自定义步骤
            steps = [
                WorkflowStep(
                    step_id=i + 1,
                    name=s.get("name", f"步骤 {i + 1}"),
                    tool=s.get("tool", ""),
                    description=s.get("description", ""),
                    params=s.get("params", {}),
                )
                for i, s in enumerate(custom_steps)
            ]
        else:
            goal_lower = goal.lower()
            builder = None
            for keywords, fn in _INTENT_RULES:
                if any(kw in goal_lower for kw in keywords):
                    builder = fn
                    break
            if builder is None:
                builder = _build_buffer_analysis  # fallback
            steps = builder(sources, goal, output_workspace)

        from .step import Workflow
        import datetime

        wf = Workflow(
            workflow_id=_make_id(),
            title=goal[:50],
            description=goal,
            data_sources=sources,
            steps=steps,
            output_workspace=output_workspace,
            created_at=datetime.datetime.now().isoformat(),
        )
        return wf.to_dict()
