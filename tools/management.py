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
        return {"success": True, "messages": msgs}
    except ImportError:
        return {"success": False, "error": "arcpy 未安装"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def add_field(
    in_table: str,
    field_name: str,
    field_type: str,
    field_length: int | None = None,
    field_alias: str = "",
    field_is_nullable: str = "NULLABLE",
) -> dict:
    return _run("arcpy.management.AddField", {
        "in_table": in_table,
        "field_name": field_name,
        "field_type": field_type,
        "field_length": field_length,
        "field_alias": field_alias,
        "field_is_nullable": field_is_nullable,
    })


def calculate_field(
    in_table: str,
    field: str,
    expression: str,
    expression_type: str = "PYTHON3",
    code_block: str = "",
    field_type: str = "",
) -> dict:
    return _run("arcpy.management.CalculateField", {
        "in_table": in_table,
        "field": field,
        "expression": expression,
        "expression_type": expression_type,
        "code_block": code_block,
        "field_type": field_type,
    })


def select_by_attribute(
    in_layer_or_view: str,
    selection_type: str = "NEW_SELECTION",
    where_clause: str = "",
    invert_where_clause: str = "NON_INVERTED",
) -> dict:
    return _run("arcpy.management.SelectLayerByAttribute", {
        "in_layer_or_view": in_layer_or_view,
        "selection_type": selection_type,
        "where_clause": where_clause,
        "invert_where_clause": invert_where_clause,
    })


def select_by_location(
    in_layer: str,
    overlap_type: str = "INTERSECT",
    select_features: str = "",
    search_distance: str = "",
    selection_type: str = "NEW_SELECTION",
) -> dict:
    return _run("arcpy.management.SelectLayerByLocation", {
        "in_layer": in_layer,
        "overlap_type": overlap_type,
        "select_features": select_features,
        "search_distance": search_distance,
        "selection_type": selection_type,
    })


def project(
    in_dataset: str,
    out_dataset: str,
    out_coor_system: str,
    transform_method: str = "",
    in_coor_system: str = "",
) -> dict:
    return _run("arcpy.management.Project", {
        "in_dataset": in_dataset,
        "out_dataset": out_dataset,
        "out_coor_system": out_coor_system,
        "transform_method": transform_method,
        "in_coor_system": in_coor_system,
    })


def copy_features(
    in_features: str,
    out_feature_class: str,
    config_keyword: str = "",
) -> dict:
    return _run("arcpy.management.CopyFeatures", {
        "in_features": in_features,
        "out_feature_class": out_feature_class,
        "config_keyword": config_keyword,
    })


def create_feature_class(
    out_path: str,
    out_name: str,
    geometry_type: str = "POLYGON",
    spatial_reference: str = "",
    has_m: str = "DISABLED",
    has_z: str = "DISABLED",
) -> dict:
    return _run("arcpy.management.CreateFeatureclass", {
        "out_path": out_path,
        "out_name": out_name,
        "geometry_type": geometry_type,
        "spatial_reference": spatial_reference,
        "has_m": has_m,
        "has_z": has_z,
    })


def clip_raster(
    in_raster: str,
    rectangle: str,
    out_raster: str,
    in_template_dataset: str = "",
    nodata_value: str = "",
    clipping_geometry: str = "NONE",
    maintain_clipping_extent: str = "NO_MAINTAIN_EXTENT",
) -> dict:
    return _run("arcpy.management.Clip", {
        "in_raster": in_raster,
        "rectangle": rectangle,
        "out_raster": out_raster,
        "in_template_dataset": in_template_dataset,
        "nodata_value": nodata_value,
        "clipping_geometry": clipping_geometry,
        "maintain_clipping_extent": maintain_clipping_extent,
    })


def delete(in_data: str) -> dict:
    return _run("arcpy.management.Delete", {"in_data": in_data})
