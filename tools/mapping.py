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


def get_current_map_info() -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")
        maps = []
        for m in aprx.listMaps():
            layers = [{"name": lyr.name, "visible": lyr.visible} for lyr in m.listLayers()]
            maps.append({"name": m.name, "layers": layers})
        return {"success": True, "maps": maps, "default_geodatabase": aprx.defaultGeodatabase}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def add_layer_to_map(
    layer_path: str,
    map_name: str = "",
    position: str = "AUTO_ARRANGE",
) -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")
        target_map = aprx.listMaps(map_name)[0] if map_name else aprx.activeMap
        lyr_file = mp.LayerFile(layer_path) if layer_path.endswith(".lyrx") or layer_path.endswith(".lyr") else None
        if lyr_file:
            target_map.addLayer(lyr_file, position)
        else:
            target_map.addDataFromPath(layer_path)
        return {"success": True, "message": f"已添加图层: {layer_path}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def apply_symbology(
    in_layer: str,
    symbology_type: str = "GRADUATED_COLORS",
    symbology_field: str = "",
    color_ramp: str = "Red-Yellow-Green",
    class_count: int = 5,
) -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if not active_map:
            return {"success": False, "error": "没有打开的地图"}

        layer = None
        for lyr in active_map.listLayers():
            if lyr.name == in_layer or lyr.dataSource == in_layer:
                layer = lyr
                break

        if layer is None:
            return {"success": False, "error": f"未找到图层: {in_layer}"}

        sym = layer.symbology
        if hasattr(sym, "updateRenderer"):
            sym.updateRenderer(symbology_type)
            if symbology_field:
                sym.renderer.classificationField = symbology_field
            if hasattr(sym.renderer, "colorRamp"):
                sym.renderer.colorRamp = aprx.listColorRamps(color_ramp)[0] if aprx.listColorRamps(color_ramp) else sym.renderer.colorRamp
            if hasattr(sym.renderer, "breakCount"):
                sym.renderer.breakCount = class_count
            layer.symbology = sym

        return {"success": True, "message": f"已应用符号化: {symbology_type}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def export_map_to_pdf(
    output_pdf: str,
    map_name: str = "",
    layout_name: str = "",
    resolution: int = 300,
) -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")

        if layout_name:
            layouts = aprx.listLayouts(layout_name)
            if layouts:
                layouts[0].exportToPDF(output_pdf, resolution=resolution)
                return {"success": True, "output": output_pdf}

        target_map = aprx.listMaps(map_name)[0] if map_name else aprx.activeMap
        if target_map:
            mxd = target_map.defaultView
            if mxd:
                mxd.exportToPDF(output_pdf, resolution=resolution)
                return {"success": True, "output": output_pdf}

        return {"success": False, "error": "未找到地图或布局"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def export_map_to_png(
    output_png: str,
    map_name: str = "",
    resolution: int = 300,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")
        target_map = aprx.listMaps(map_name)[0] if map_name else aprx.activeMap
        if target_map:
            view = target_map.defaultView
            if view:
                view.exportToPNG(output_png, width=width, height=height, resolution=resolution)
                return {"success": True, "output": output_png}
        return {"success": False, "error": "未找到地图"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_layouts() -> dict:
    try:
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject("CURRENT")
        layouts = [{"name": lyt.name, "page_height": lyt.pageHeight, "page_width": lyt.pageWidth} for lyt in aprx.listLayouts()]
        return {"success": True, "layouts": layouts}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
