from __future__ import annotations
from typing import Any


def get_tool_schema(tool_path: str) -> dict[str, Any]:
    """
    从 arcpy 提取工具参数 schema，用于 UI 编辑器和 AI 规划。
    tool_path 格式: "analysis.Buffer" 或 "sa.Slope"
    """
    try:
        import arcpy  # type: ignore
        parts = tool_path.split(".")
        obj = arcpy
        for part in parts:
            obj = getattr(obj, part)

        params = []
        for p in obj.parameters:
            param_info: dict[str, Any] = {
                "name": p.name,
                "display_name": p.displayName,
                "type": p.datatype,
                "required": p.parameterType == "Required",
                "direction": p.direction,
                "default": p.defaultEnvironmentName,
                "filter": None,
            }
            try:
                if p.filter and p.filter.list:
                    param_info["filter"] = p.filter.list
            except Exception:
                pass
            params.append(param_info)

        return {
            "tool": tool_path,
            "label": getattr(obj, "label", tool_path),
            "description": getattr(obj, "description", ""),
            "parameters": params,
        }
    except Exception as exc:
        return {"tool": tool_path, "error": str(exc), "parameters": []}


def list_toolboxes() -> list[dict[str, str]]:
    return [
        {"name": "3D Analyst",          "alias": "ddd",          "module": "arcpy.ddd"},
        {"name": "Analysis",            "alias": "analysis",     "module": "arcpy.analysis"},
        {"name": "Cartography",         "alias": "cartography",  "module": "arcpy.cartography"},
        {"name": "Conversion",          "alias": "conversion",   "module": "arcpy.conversion"},
        {"name": "Data Management",     "alias": "management",   "module": "arcpy.management"},
        {"name": "Editing",             "alias": "edit",         "module": "arcpy.edit"},
        {"name": "GeoAI",               "alias": "geoai",        "module": "arcpy.geoai"},
        {"name": "Geostatistical Analyst", "alias": "ga",        "module": "arcpy.ga"},
        {"name": "Network Analyst",     "alias": "na",           "module": "arcpy.na"},
        {"name": "Spatial Analyst",     "alias": "sa",           "module": "arcpy.sa"},
        {"name": "Spatial Statistics",  "alias": "stats",        "module": "arcpy.stats"},
        {"name": "Space Time Pattern Mining", "alias": "stpm",   "module": "arcpy.stpm"},
        {"name": "Multidimension",      "alias": "md",           "module": "arcpy.md"},
        {"name": "Raster Analysis",     "alias": "ra",           "module": "arcpy.ra"},
        {"name": "Image Analyst",       "alias": "ia",           "module": "arcpy.ia"},
    ]


def search_tools(keyword: str) -> list[dict[str, str]]:
    """在所有工具箱中搜索匹配关键字的工具（不需要 arcpy 运行时）"""
    keyword_lower = keyword.lower()
    # 静态工具名称索引，覆盖高频工具
    _TOOL_INDEX = [
        ("analysis.Buffer", "缓冲区", "Creates buffer polygons around input features"),
        ("analysis.Clip", "裁剪（矢量）", "Clips features to the extent of clip features"),
        ("analysis.Intersect", "交集", "Computes the geometric intersection of input features"),
        ("analysis.Union", "合并", "Computes the union of input features"),
        ("analysis.Erase", "差集", "Erases portions of features that overlap erase features"),
        ("analysis.SpatialJoin", "空间连接", "Joins attributes from one feature to another based on spatial relationship"),
        ("analysis.Select", "按属性选择导出", "Selects features based on an attribute query"),
        ("analysis.Near", "近邻分析", "Calculates distance to nearest feature"),
        ("analysis.PointDistance", "点距离", "Calculates distances between points"),
        ("management.CalculateField", "计算字段", "Calculates values for a field"),
        ("management.AddField", "添加字段", "Adds a new field to a table"),
        ("management.SelectLayerByAttribute", "按属性选择", "Adds, updates, or removes a selection based on an attribute query"),
        ("management.SelectLayerByLocation", "按位置选择", "Adds, updates, or removes a selection based on spatial relationship"),
        ("management.Clip", "裁剪栅格", "Clips a raster to an extent or feature class boundary"),
        ("management.Dissolve", "融合", "Aggregates features based on attribute values"),
        ("management.Project", "投影变换", "Projects spatial data from one coordinate system to another"),
        ("management.MergeEditing", "合并要素", "Merges features from multiple feature classes"),
        ("management.CopyFeatures", "复制要素", "Copies features to a new feature class"),
        ("management.Delete", "删除", "Deletes data from disk"),
        ("sa.Slope", "坡度", "Identifies the rate of maximum change in value from each cell to its neighbors"),
        ("sa.Aspect", "坡向", "Derives the aspect from each cell of a raster surface"),
        ("sa.HillShade", "山体阴影", "Creates a shaded relief from a surface raster"),
        ("sa.Viewshed", "视域分析", "Determines the raster surface locations visible to a set of observer features"),
        ("sa.KernelDensity", "核密度", "Calculates a magnitude-per-unit area from point or polyline features"),
        ("sa.PointDensity", "点密度", "Calculates a magnitude-per-unit area from point features in a neighborhood"),
        ("sa.Reclassify", "重分类", "Reclassifies values in a raster"),
        ("sa.ZonalStatisticsAsTable", "分区统计", "Calculates statistics on values of a raster within the zones of another dataset"),
        ("sa.Con", "条件判断", "Performs conditional logic on raster values"),
        ("sa.RasterCalculator", "栅格计算器", "Builds and executes a single Map Algebra expression"),
        ("na.MakeRouteAnalysisLayer", "路径分析", "Makes a route analysis layer"),
        ("na.MakeServiceAreaAnalysisLayer", "服务区分析", "Makes a service area analysis layer"),
        ("na.MakeClosestFacilityAnalysisLayer", "最近设施点", "Makes a closest facility analysis layer"),
        ("na.MakeODCostMatrixAnalysisLayer", "OD成本矩阵", "Makes an OD cost matrix analysis layer"),
        ("na.AddLocations", "添加网络位置", "Adds network locations to a network analysis layer"),
        ("na.Solve", "网络求解", "Solves the network analysis problem"),
        ("stats.HotSpots", "热点分析", "Calculates the Getis-Ord Gi* statistic for each feature"),
        ("stats.ClusterAndOutlierAnalysis", "聚类和异常值分析", "Given a set of weighted features, identifies statistically significant clusters and spatial outliers"),
        ("stats.SpatialAutocorrelation", "空间自相关", "Measures spatial autocorrelation based on feature locations and attribute values"),
        ("stats.DirectionalDistribution", "方向分布", "Creates standard deviational ellipses to summarize the spatial characteristics"),
        ("ga.EmpiricalBayesianKriging", "经验贝叶斯克里金", "Interpolates values using Empirical Bayesian Kriging"),
        ("ga.IDW", "反距离权重插值", "Interpolates a surface from points using an inverse distance weighted technique"),
        ("geoai.DetectObjectsUsingDeepLearning", "深度学习目标检测", "Runs inference on raster data using a deep learning model"),
        ("geoai.ClassifyPixelsUsingDeepLearning", "深度学习像素分类", "Classifies pixels using a deep learning model"),
    ]

    results = []
    for tool_path, zh_name, desc in _TOOL_INDEX:
        if (keyword_lower in tool_path.lower()
                or keyword_lower in zh_name
                or keyword_lower in desc.lower()):
            results.append({
                "tool": tool_path,
                "name_zh": zh_name,
                "description": desc,
            })
    return results
