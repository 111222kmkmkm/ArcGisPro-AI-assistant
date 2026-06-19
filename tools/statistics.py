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
        return {"success": False, "error": "arcpy 未安装"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def hot_spots(
    input_feature_class: str,
    input_field: str,
    output_feature_class: str,
    conceptualization: str = "FIXED_DISTANCE_BAND",
    distance_method: str = "EUCLIDEAN_DISTANCE",
    standardization: str = "ROW",
    distance_band: float = 0,
    self_potential_field: str = "",
    weights_matrix_file: str = "",
) -> dict:
    return _run("arcpy.stats.HotSpots", {
        "Input_Feature_Class": input_feature_class,
        "Input_Field": input_field,
        "Output_Feature_Class": output_feature_class,
        "Conceptualization_of_Spatial_Relationships": conceptualization,
        "Distance_Method": distance_method,
        "Standardization": standardization,
        "Distance_Band_or_Threshold_Distance": distance_band,
        "Self_Potential_Field": self_potential_field,
        "Weights_Matrix_File": weights_matrix_file,
    })


def cluster_outlier_analysis(
    input_feature_class: str,
    input_field: str,
    output_feature_class: str,
    conceptualization: str = "INVERSE_DISTANCE",
    distance_method: str = "EUCLIDEAN_DISTANCE",
    standardization: str = "ROW",
    distance_band: float = 0,
) -> dict:
    return _run("arcpy.stats.ClusterAndOutlierAnalysis", {
        "Input_Feature_Class": input_feature_class,
        "Input_Field": input_field,
        "Output_Feature_Class": output_feature_class,
        "Conceptualization_of_Spatial_Relationships": conceptualization,
        "Distance_Method": distance_method,
        "Standardization": standardization,
        "Distance_Band_or_Threshold_Distance": distance_band,
    })


def spatial_autocorrelation(
    input_feature_class: str,
    input_field: str,
    generate_report: str = "NO_REPORT",
    conceptualization: str = "INVERSE_DISTANCE",
    distance_method: str = "EUCLIDEAN_DISTANCE",
    standardization: str = "ROW",
    distance_band: float = 0,
) -> dict:
    return _run("arcpy.stats.SpatialAutocorrelation", {
        "Input_Feature_Class": input_feature_class,
        "Input_Field": input_field,
        "Generate_Report": generate_report,
        "Conceptualization_of_Spatial_Relationships": conceptualization,
        "Distance_Method": distance_method,
        "Standardization": standardization,
        "Distance_Band_or_Threshold_Distance": distance_band,
    })


def optimized_hot_spot_analysis(
    input_features: str,
    output_features: str,
    analysis_field: str = "",
    incident_data_aggregation_method: str = "COUNT_INCIDENTS_WITHIN_FISHNET_POLYGONS",
    bounding_polygons_defining_where_incidents_are_possible: str = "",
    polygons_for_aggregating_incidents_into_counts: str = "",
) -> dict:
    return _run("arcpy.stats.OptimizedHotSpotAnalysis", {
        "Input_Features": input_features,
        "Output_Features": output_features,
        "Analysis_Field": analysis_field,
        "Incident_Data_Aggregation_Method": incident_data_aggregation_method,
        "Bounding_Polygons_Defining_Where_Incidents_Are_Possible": bounding_polygons_defining_where_incidents_are_possible,
        "Polygons_for_Aggregating_Incidents_into_Counts": polygons_for_aggregating_incidents_into_counts,
    })


def space_time_cube(
    in_features: str,
    output_cube: str,
    time_field: str,
    time_step_interval: str,
    time_step_alignment: str = "END_TIME",
    reference_time: str = "",
    distance_interval: str = "",
) -> dict:
    return _run("arcpy.stpm.CreateSpaceTimeCube", {
        "in_features": in_features,
        "output_cube": output_cube,
        "time_field": time_field,
        "time_step_interval": time_step_interval,
        "time_step_alignment": time_step_alignment,
        "reference_time": reference_time,
        "distance_interval": distance_interval,
    })


def emerging_hot_spots(
    in_cube: str,
    analysis_variable: str,
    output_features: str,
    neighborhood_distance: str = "",
    neighborhood_time_step: int = 1,
    polygon_mask: str = "",
) -> dict:
    return _run("arcpy.stpm.EmergingHotSpotAnalysis", {
        "in_cube": in_cube,
        "analysis_variable": analysis_variable,
        "output_features": output_features,
        "neighborhood_distance": neighborhood_distance,
        "neighborhood_time_step": neighborhood_time_step,
        "polygon_mask": polygon_mask,
    })
