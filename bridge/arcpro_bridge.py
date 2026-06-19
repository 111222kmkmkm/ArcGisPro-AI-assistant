from __future__ import annotations
from typing import Any
from .named_pipe import NamedPipeClient


class ArcProBridge:
    """
    Bridge between MCP Server and ArcGIS Pro.

    - GIS computation (arcpy tools): runs directly via arcpy in-process.
    - Map/UI control: sent via Named Pipe to the Add-In running inside Pro.
    """

    def __init__(self) -> None:
        self._pipe = NamedPipeClient()

    # ------------------------------------------------------------------
    # Direct arcpy operations (no Pro UI needed)
    # ------------------------------------------------------------------

    def get_arcpy_env(self) -> dict:
        try:
            import arcpy  # type: ignore
            return {
                "workspace": arcpy.env.workspace,
                "scratch_workspace": arcpy.env.scratchWorkspace,
                "overwrite_output": arcpy.env.overwriteOutput,
                "output_coordinate_system": str(arcpy.env.outputCoordinateSystem),
                "cell_size": arcpy.env.cellSize,
            }
        except ImportError:
            return {"error": "arcpy not available"}

    def set_arcpy_env(self, settings: dict[str, Any]) -> dict:
        try:
            import arcpy  # type: ignore
            for key, value in settings.items():
                setattr(arcpy.env, key, value)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def describe_data(self, path: str) -> dict:
        try:
            import arcpy  # type: ignore
            desc = arcpy.Describe(path)
            return {
                "name": desc.name,
                "data_type": desc.dataType,
                "shape_type": getattr(desc, "shapeType", None),
                "spatial_reference": getattr(getattr(desc, "spatialReference", None), "name", None),
                "extent": str(getattr(desc, "extent", None)),
                "fields": [
                    {"name": f.name, "type": f.type, "length": f.length}
                    for f in getattr(desc, "fields", [])
                ],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def list_feature_classes(self, workspace: str) -> dict:
        try:
            import arcpy  # type: ignore
            arcpy.env.workspace = workspace
            fcs = arcpy.ListFeatureClasses() or []
            rasters = arcpy.ListRasters() or []
            tables = arcpy.ListTables() or []
            return {
                "workspace": workspace,
                "feature_classes": fcs,
                "rasters": rasters,
                "tables": tables,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def check_extensions(self) -> dict:
        try:
            import arcpy  # type: ignore
            extensions = ["Spatial", "Network", "3D", "GeoStats", "GeoAI", "Intelligence"]
            status: dict[str, str] = {}
            for ext in extensions:
                try:
                    status[ext] = arcpy.CheckExtension(ext)
                except Exception:
                    status[ext] = "Unknown"
            return status
        except ImportError:
            return {"error": "arcpy not available"}

    # ------------------------------------------------------------------
    # ArcGIS Pro UI operations (via Named Pipe → Add-In)
    # ------------------------------------------------------------------

    def zoom_to_layer(self, layer_name: str) -> dict:
        return self._pipe.send_command({"action": "zoom_to_layer", "layer_name": layer_name})

    def set_layer_visibility(self, layer_name: str, visible: bool) -> dict:
        return self._pipe.send_command({
            "action": "set_layer_visibility",
            "layer_name": layer_name,
            "visible": visible,
        })

    def add_layer_to_map(self, layer_path: str, map_name: str = "") -> dict:
        return self._pipe.send_command({
            "action": "add_layer",
            "layer_path": layer_path,
            "map_name": map_name,
        })

    def get_current_extent(self) -> dict:
        return self._pipe.send_command({"action": "get_extent"})

    def set_extent(self, xmin: float, ymin: float, xmax: float, ymax: float) -> dict:
        return self._pipe.send_command({
            "action": "set_extent",
            "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
        })

    def open_attribute_table(self, layer_name: str) -> dict:
        return self._pipe.send_command({"action": "open_attribute_table", "layer_name": layer_name})

    def export_map(self, output_path: str, resolution: int = 300) -> dict:
        return self._pipe.send_command({
            "action": "export_map",
            "output_path": output_path,
            "resolution": resolution,
        })

    def push_workflow_to_ui(self, workflow_dict: dict) -> dict:
        """Send workflow JSON to the Add-In's WorkflowDockPane for visualization."""
        return self._pipe.send_notification({
            "action": "show_workflow",
            "workflow": workflow_dict,
        })

    def update_step_status_in_ui(self, workflow_id: str, step_id: int, status: str, message: str = "") -> dict:
        return self._pipe.send_notification({
            "action": "update_step_status",
            "workflow_id": workflow_id,
            "step_id": step_id,
            "status": status,
            "message": message,
        })

    def is_pro_running(self) -> bool:
        return self._pipe.is_pro_running()
