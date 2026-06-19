from __future__ import annotations
from typing import Any


def _run(tool_path: str, params: dict[str, Any]) -> dict:
    try:
        import arcpy  # type: ignore
        parts = tool_path.split(".")
        obj = arcpy
        for part in parts[1:]:
            obj = getattr(obj, part)
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        result = obj(**clean)
        msgs = []
        if hasattr(result, "messageCount"):
            msgs = [result.getMessage(i) for i in range(result.messageCount)]
        return {"success": True, "messages": msgs, "result": str(result)}
    except ImportError:
        return {"success": False, "error": "arcpy 未安装，请使用 arcgispro-py3 环境"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---- Vector Analysis Tools -------------------------------------------

def buffer(
    in_features: str,
    out_feature_class: str,
    buffer_distance_or_field: str,
    line_side: str = "FULL",
    line_end_type: str = "ROUND",
    dissolve_option: str = "NONE",
    dissolve_field: list[str] | None = None,
    method: str = "PLANAR",
) -> dict:
    return _run("arcpy.analysis.Buffer", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "buffer_distance_or_field": buffer_distance_or_field,
        "line_side": line_side,
        "line_end_type": line_end_type,
        "dissolve_option": dissolve_option,
        "dissolve_field": dissolve_field,
        "method": method,
    })


def clip(
    in_features: str,
    clip_features: str,
    out_feature_class: str,
    cluster_tolerance: str = "",
) -> dict:
    return _run("arcpy.analysis.Clip", {
        "in_features": in_features,
        "clip_features": clip_features,
        "out_feature_class": out_feature_class,
        "cluster_tolerance": cluster_tolerance,
    })


def intersect(
    in_features: list[str],
    out_feature_class: str,
    join_attributes: str = "ALL",
    cluster_tolerance: str = "",
    output_type: str = "INPUT",
) -> dict:
    return _run("arcpy.analysis.Intersect", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "join_attributes": join_attributes,
        "cluster_tolerance": cluster_tolerance,
        "output_type": output_type,
    })


def union(
    in_features: list[str],
    out_feature_class: str,
    join_attributes: str = "ALL",
    cluster_tolerance: str = "",
    gaps: str = "GAPS",
) -> dict:
    return _run("arcpy.analysis.Union", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "join_attributes": join_attributes,
        "cluster_tolerance": cluster_tolerance,
        "gaps": gaps,
    })


def erase(
    in_features: str,
    erase_features: str,
    out_feature_class: str,
    cluster_tolerance: str = "",
) -> dict:
    return _run("arcpy.analysis.Erase", {
        "in_features": in_features,
        "erase_features": erase_features,
        "out_feature_class": out_feature_class,
        "cluster_tolerance": cluster_tolerance,
    })


def spatial_join(
    target_features: str,
    join_features: str,
    out_feature_class: str,
    join_operation: str = "JOIN_ONE_TO_ONE",
    join_type: str = "KEEP_ALL",
    match_option: str = "INTERSECT",
    search_radius: str = "",
    distance_field_name: str = "",
) -> dict:
    return _run("arcpy.analysis.SpatialJoin", {
        "target_features": target_features,
        "join_features": join_features,
        "out_feature_class": out_feature_class,
        "join_operation": join_operation,
        "join_type": join_type,
        "match_option": match_option,
        "search_radius": search_radius,
        "distance_field_name": distance_field_name,
    })


def select(
    in_features: str,
    out_feature_class: str,
    where_clause: str = "",
) -> dict:
    return _run("arcpy.analysis.Select", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "where_clause": where_clause,
    })


def near(
    in_features: str,
    near_features: str | list[str],
    search_radius: str = "",
    location: str = "NO_LOCATION",
    angle: str = "NO_ANGLE",
    method: str = "PLANAR",
) -> dict:
    return _run("arcpy.analysis.Near", {
        "in_features": in_features,
        "near_features": near_features,
        "search_radius": search_radius,
        "location": location,
        "angle": angle,
        "method": method,
    })


def dissolve(
    in_features: str,
    out_feature_class: str,
    dissolve_field: list[str] | None = None,
    statistics_fields: list[list[str]] | None = None,
    multi_part: str = "MULTI_PART",
    unsplit_lines: str = "DISSOLVE_LINES",
) -> dict:
    return _run("arcpy.management.Dissolve", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "dissolve_field": dissolve_field,
        "statistics_fields": statistics_fields,
        "multi_part": multi_part,
        "unsplit_lines": unsplit_lines,
    })
