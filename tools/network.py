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
        return {"success": False, "error": "arcpy / Network Analyst 未安装"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def make_route_layer(
    network_data_source: str,
    layer_name: str = "Route",
    travel_mode: str = "Driving Time",
    time_of_day: str | None = None,
    time_zone: str = "LOCAL_TIME_AT_LOCATIONS",
    output_path_shape: str = "TRUE_LINES_WITH_MEASURES",
) -> dict:
    return _run("arcpy.na.MakeRouteAnalysisLayer", {
        "network_data_source": network_data_source,
        "layer_name": layer_name,
        "travel_mode": travel_mode,
        "time_of_day": time_of_day,
        "time_zone": time_zone,
        "output_path_shape": output_path_shape,
    })


def make_service_area_layer(
    network_data_source: str,
    layer_name: str = "ServiceArea",
    travel_mode: str = "Driving Time",
    travel_direction: str = "FROM_FACILITIES",
    cutoffs: list[float] | None = None,
    time_of_day: str | None = None,
    geometry_at_cutoff: str = "RINGS",
    geometry_at_overlap: str = "OVERLAP",
) -> dict:
    return _run("arcpy.na.MakeServiceAreaAnalysisLayer", {
        "network_data_source": network_data_source,
        "layer_name": layer_name,
        "travel_mode": travel_mode,
        "travel_direction": travel_direction,
        "cutoffs": cutoffs or [5, 10, 15],
        "time_of_day": time_of_day,
        "geometry_at_cutoff": geometry_at_cutoff,
        "geometry_at_overlap": geometry_at_overlap,
    })


def make_od_cost_matrix_layer(
    network_data_source: str,
    layer_name: str = "OD Cost Matrix",
    travel_mode: str = "Driving Time",
    cutoff: float | None = None,
    number_of_destinations_to_find: int | None = None,
) -> dict:
    return _run("arcpy.na.MakeODCostMatrixAnalysisLayer", {
        "network_data_source": network_data_source,
        "layer_name": layer_name,
        "travel_mode": travel_mode,
        "cutoff": cutoff,
        "number_of_destinations_to_find": number_of_destinations_to_find,
    })


def make_closest_facility_layer(
    network_data_source: str,
    layer_name: str = "ClosestFacility",
    travel_mode: str = "Driving Time",
    travel_direction: str = "FROM_FACILITIES",
    cutoff: float | None = None,
    number_of_facilities_to_find: int = 1,
) -> dict:
    return _run("arcpy.na.MakeClosestFacilityAnalysisLayer", {
        "network_data_source": network_data_source,
        "layer_name": layer_name,
        "travel_mode": travel_mode,
        "travel_direction": travel_direction,
        "cutoff": cutoff,
        "number_of_facilities_to_find": number_of_facilities_to_find,
    })


def add_locations(
    in_network_analysis_layer: str,
    sub_layer: str,
    in_table: str,
    field_mappings: str = "",
    search_tolerance: str = "5000 Meters",
    sort_field: str = "",
    search_criteria: str = "",
    match_type: str = "MATCH_TO_CLOSEST",
    append: str = "APPEND",
    snap_to_position_along_network: str = "NO_SNAP",
) -> dict:
    return _run("arcpy.na.AddLocations", {
        "in_network_analysis_layer": in_network_analysis_layer,
        "sub_layer": sub_layer,
        "in_table": in_table,
        "field_mappings": field_mappings,
        "search_tolerance": search_tolerance,
        "sort_field": sort_field,
        "search_criteria": search_criteria,
        "match_type": match_type,
        "append": append,
        "snap_to_position_along_network": snap_to_position_along_network,
    })


def solve(
    in_network_analysis_layer: str,
    ignore_invalids: str = "SKIP",
    terminate_on_solve_error: str = "TERMINATE",
    simplification_tolerance: str = "",
) -> dict:
    return _run("arcpy.na.Solve", {
        "in_network_analysis_layer": in_network_analysis_layer,
        "ignore_invalids": ignore_invalids,
        "terminate_on_solve_error": terminate_on_solve_error,
        "simplification_tolerance": simplification_tolerance,
    })
