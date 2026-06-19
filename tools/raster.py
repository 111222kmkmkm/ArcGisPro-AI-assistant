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
        return {"success": False, "error": "arcpy / Spatial Analyst 未安装"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def slope(
    in_raster: str,
    out_raster: str,
    output_measurement: str = "DEGREE",
    z_factor: float = 1.0,
    method: str = "PLANAR",
    z_unit: str = "METER",
) -> dict:
    return _run("arcpy.sa.Slope", {
        "in_raster": in_raster,
        "out_raster": out_raster,
        "output_measurement": output_measurement,
        "z_factor": z_factor,
        "method": method,
        "z_unit": z_unit,
    })


def aspect(in_raster: str, out_raster: str, method: str = "PLANAR") -> dict:
    return _run("arcpy.sa.Aspect", {
        "in_raster": in_raster,
        "out_raster": out_raster,
        "method": method,
    })


def hillshade(
    in_raster: str,
    out_raster: str,
    azimuth: float = 315.0,
    altitude: float = 45.0,
    model_shadows: str = "NO_SHADOWS",
    z_factor: float = 1.0,
) -> dict:
    return _run("arcpy.sa.HillShade", {
        "in_raster": in_raster,
        "out_raster": out_raster,
        "azimuth": azimuth,
        "altitude": altitude,
        "model_shadows": model_shadows,
        "z_factor": z_factor,
    })


def viewshed(
    in_raster: str,
    in_observer_features: str,
    out_raster: str,
    z_factor: float = 1.0,
    curvature_correction: str = "FLAT_EARTH",
    refractivity_coefficient: float = 0.13,
) -> dict:
    return _run("arcpy.sa.Viewshed2", {
        "in_raster": in_raster,
        "in_observer_features": in_observer_features,
        "out_raster": out_raster,
        "z_factor": z_factor,
        "curvature_correction": curvature_correction,
        "refractivity_coefficient": refractivity_coefficient,
    })


def kernel_density(
    in_features: str,
    out_raster: str,
    population_field: str = "NONE",
    cell_size: float = 0,
    search_radius: float = 0,
    area_unit_scale_factor: str = "SQUARE_KILOMETERS",
    out_cell_values: str = "DENSITIES",
    method: str = "PLANAR",
) -> dict:
    return _run("arcpy.sa.KernelDensity", {
        "in_features": in_features,
        "population_field": population_field,
        "out_raster": out_raster,
        "cell_size": cell_size,
        "search_radius": search_radius,
        "area_unit_scale_factor": area_unit_scale_factor,
        "out_cell_values": out_cell_values,
        "method": method,
    })


def reclassify(
    in_raster: str,
    out_raster: str,
    reclass_field: str = "Value",
    remap: str = "",
    missing_values: str = "DATA",
) -> dict:
    return _run("arcpy.sa.Reclassify", {
        "in_raster": in_raster,
        "reclass_field": reclass_field,
        "remap": remap,
        "out_raster": out_raster,
        "missing_values": missing_values,
    })


def zonal_statistics_as_table(
    in_zone_data: str,
    zone_field: str,
    in_value_raster: str,
    out_table: str,
    ignore_nodata: str = "DATA",
    statistics_type: str = "ALL",
) -> dict:
    return _run("arcpy.sa.ZonalStatisticsAsTable", {
        "in_zone_data": in_zone_data,
        "zone_field": zone_field,
        "in_value_raster": in_value_raster,
        "out_table": out_table,
        "ignore_nodata": ignore_nodata,
        "statistics_type": statistics_type,
    })


def raster_calculator(expression: str, output_raster: str) -> dict:
    return _run("arcpy.sa.RasterCalculator", {
        "expression": expression,
        "output_raster": output_raster,
    })


def con(
    in_conditional_raster: str,
    in_true_raster_or_constant: Any,
    in_false_raster_or_constant: Any = None,
    where_clause: str = "",
    out_raster: str = "",
) -> dict:
    params: dict[str, Any] = {
        "in_conditional_raster": in_conditional_raster,
        "in_true_raster_or_constant": in_true_raster_or_constant,
    }
    if in_false_raster_or_constant is not None:
        params["in_false_raster_or_constant"] = in_false_raster_or_constant
    if where_clause:
        params["where_clause"] = where_clause
    if out_raster:
        params["out_raster"] = out_raster
    return _run("arcpy.sa.Con", params)


def idw(
    in_point_features: str,
    z_field: str,
    out_raster: str,
    cell_size: float = 0,
    power: float = 2.0,
    search_radius: str = "VARIABLE 12",
) -> dict:
    return _run("arcpy.sa.Idw", {
        "in_point_features": in_point_features,
        "z_field": z_field,
        "out_raster": out_raster,
        "cell_size": cell_size,
        "power": power,
        "search_radius": search_radius,
    })
