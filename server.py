"""
ArcGIS Pro MCP Server

放置位置:
    将整个 mcp_arcgis/ 目录放在 ArcGIS Pro 安装根目录下，
    与 bin/、Resources/ 同级。目录结构:
        <ArcGIS Pro 安装根目录>/
            bin/
            Resources/
            mcp_arcgis/       ← 插件目录
                server.py     ← 本文件

启动命令 (MCP 客户端 args 字段):
    ["<安装根目录>/bin/Python/envs/arcgispro-py3/python.exe",
     "<安装根目录>/mcp_arcgis/server.py"]
"""
from __future__ import annotations
import json
import sys
import os
import datetime
from typing import Any

_LOG_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "mcp_server_log.txt")

def _log(msg: str):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%H:%M:%S.%f}] {msg}\n")
    except Exception:
        pass

# 从本文件位置向上一层推导 ArcGIS Pro 安装根目录
# 结构: <pro_root>/mcp_arcgis/server.py
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PRO_ROOT = os.environ.get("ARCGIS_PRO_PATH", os.path.dirname(_THIS_DIR))

_ARCPY_PATH = os.path.join(_PRO_ROOT, "Resources", "ArcPy")
if _ARCPY_PATH not in sys.path:
    sys.path.insert(0, _ARCPY_PATH)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except ImportError:
    print("ERROR: mcp package not found. Install: pip install 'mcp[cli]'", file=sys.stderr)
    sys.exit(1)

from workflow import WorkflowEngine, WorkflowPlanner
from bridge import ArcProBridge, NamedPipeChatServer, AIChatService
from resources.toolbox_schema import get_tool_schema, search_tools, list_toolboxes
import tools as arc_tools

# ---- load config --------------------------------------------------------
_CFG_PATH = os.path.join(_THIS_DIR, "config.json")
_CFG: dict = {}
if os.path.isfile(_CFG_PATH):
    with open(_CFG_PATH, encoding="utf-8") as _f:
        _CFG = json.load(_f)

# ---- global state -------------------------------------------------------
_engine = WorkflowEngine()
_planner = WorkflowPlanner()
_bridge = ArcProBridge()
_current_step_counter = 0
_chat_svc = AIChatService()

# configure chat service from config
if _CFG.get("anthropic_api_key"):
    _chat_svc.configure(
        api_key=_CFG["anthropic_api_key"],
        model=_CFG.get("model", "claude-sonnet-4-6"),
        base_url=_CFG.get("base_url", ""),
        language=_CFG.get("language", "zh"),
    )

mcp = FastMCP("arcgis-pro-mcp")


# ---- Chat Pipe: receives messages from ArcGIS Pro Add-In ----------------

def _tool_executor(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name, mirror of server.py tool handlers."""
    global _current_step_counter
    _log(f"TOOL_CALL: {tool_name} | input={json.dumps(tool_input, ensure_ascii=False)[:500]}")
    try:
        if tool_name == "plan_workflow":
            custom_steps = tool_input.get("steps", None)
            wf_dict = _planner.plan(
                goal=tool_input["goal"],
                data_sources=tool_input["data_sources"],
                output_workspace=tool_input.get("output_workspace", ""),
                custom_steps=custom_steps,
            )
            _engine.load_workflow(wf_dict)
            _log(f"  plan_workflow: steps={len(wf_dict['steps'])}, pushing to UI...")
            push_result = _bridge.push_workflow_to_ui(wf_dict)
            _log(f"  push_workflow result: {push_result}")
            return json.dumps({"workflow_id": wf_dict["workflow_id"], "title": wf_dict["title"],
                                "steps": len(wf_dict["steps"])}, ensure_ascii=False)

        elif tool_name == "execute_workflow":
            def _status_cb(step_id, status, message):
                _bridge.update_step_status_in_ui("", step_id, status, message)
            result = _engine.execute(
                tool_input["workflow_id"],
                from_step=tool_input.get("from_step", 1),
                to_step=tool_input.get("to_step") or None,
                status_callback=_status_cb,
            )
            if result.get("overall_success"):
                _auto_add_outputs_to_map(result)
            return json.dumps(result, ensure_ascii=False)

        elif tool_name == "execute_single_tool":
            import arcpy  # type: ignore
            tool_path = tool_input["tool_path"]
            parts = tool_path.split(".")
            obj = arcpy
            for part in parts:
                obj = getattr(obj, part)
            clean = {k: v for k, v in tool_input.get("params", {}).items() if v is not None}
            res = obj(**clean)
            msgs = [res.getMessage(i) for i in range(res.messageCount)] if hasattr(res, "messageCount") else []

            # 自动添加输出到地图
            for key in ("out_feature_class", "out_raster", "output_raster", "Output_Feature_Class"):
                path = clean.get(key, "")
                if path:
                    _bridge.add_layer_to_map(path)
                    break

            return json.dumps({"success": True, "messages": msgs}, ensure_ascii=False)

        elif tool_name == "describe_data":
            return json.dumps(_bridge.describe_data(tool_input["path"]), ensure_ascii=False)

        elif tool_name == "list_workspace_data":
            return json.dumps(_bridge.list_feature_classes(tool_input["workspace"]), ensure_ascii=False)

        elif tool_name == "search_gis_tools":
            return json.dumps(search_tools(tool_input["keyword"]), ensure_ascii=False)

        elif tool_name == "zoom_to_layer":
            return json.dumps(_bridge.zoom_to_layer(tool_input["layer_name"]), ensure_ascii=False)

        elif tool_name == "set_layer_visibility":
            return json.dumps(_bridge.set_layer_visibility(
                tool_input["layer_name"], tool_input["visible"]), ensure_ascii=False)

        elif tool_name == "get_map_info":
            return json.dumps(arc_tools.get_current_map_info(), ensure_ascii=False)

        elif tool_name == "set_arcpy_env":
            return json.dumps(_bridge.set_arcpy_env(tool_input), ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    except ImportError:
        return json.dumps({"error": "arcpy 未安装，请使用 arcgispro-py3 环境"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


_WORKFLOW_KEYWORDS = [
    "工作流", "步骤链", "workflow", "分析流程",
    "缓冲", "buffer", "空间连接", "spatial join",
    "热点", "hotspot", "密度分析", "density",
    "裁剪", "clip", "坡度", "slope", "坡向", "aspect",
    "路径", "route", "服务区", "service area",
    "ndvi", "植被", "人口密度",
]


def _contains_workflow_intent(messages: list[dict]) -> bool:
    """检测最近的用户消息是否包含工作流/分析意图。"""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                content_lower = content.lower()
                return any(kw in content_lower for kw in _WORKFLOW_KEYWORDS)
    return False


def _auto_generate_workflow(messages: list[dict]):
    """从用户消息中提取意图，自动生成工作流并推送到 UI。"""
    # 提取最后一条用户消息
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_text = content
                break

    if not user_text:
        return

    _log(f"AUTO_WORKFLOW: user_text={user_text[:200]}")

    # 用 planner 匹配意图
    try:
        wf_dict = _planner.plan(
            goal=user_text,
            data_sources=[],  # 无数据源，用户需后续指定
            output_workspace="",
        )
        _engine.load_workflow(wf_dict)
        _log(f"AUTO_WORKFLOW: generated {len(wf_dict['steps'])} steps, pushing to UI...")
        push_result = _bridge.push_workflow_to_ui(wf_dict)
        _log(f"AUTO_WORKFLOW: push_result={push_result}")
    except Exception as exc:
        _log(f"AUTO_WORKFLOW error: {exc}")


def _auto_add_outputs_to_map(result: dict):
    """执行成功后，自动将输出图层添加到地图。"""
    try:
        for step_result in result.get("results", []):
            if not step_result.get("success"):
                continue
            # 从 workflow 的 steps 中找到对应的 outputs
            wf = result.get("workflow", {})
            for step in wf.get("steps", []):
                if step.get("step_id") == step_result.get("step_id"):
                    params = step.get("params", {})
                    # 尝试找到输出路径字段
                    for key in ("out_feature_class", "out_raster", "output_raster", "Output_Feature_Class"):
                        path = params.get(key, "")
                        if path and not path.startswith("<") and not path.startswith("${"):
                            _log(f"AUTO_ADD: adding {path} to map")
                            push_result = _bridge.add_layer_to_map(path)
                            _log(f"AUTO_ADD: result={push_result}")
                            break
    except Exception as exc:
        _log(f"AUTO_ADD error: {exc}")


def _handle_chat_command(command: dict) -> dict:
    action = command.get("action", "")

    if action == "ping":
        return {"success": True, "message": "arcgis-pro-mcp chat server ready"}

    if action == "configure":
        api_key = command.get("api_key", "")
        model = command.get("model", "claude-sonnet-4-6")
        base_url = command.get("base_url", "")
        language = command.get("language", "zh")
        if api_key:
            _chat_svc.configure(
                api_key=api_key,
                model=model,
                base_url=base_url,
                language=language,
            )
            # persist to config
            _CFG["anthropic_api_key"] = api_key
            _CFG["model"] = model
            _CFG["base_url"] = base_url
            _CFG["language"] = language
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(_CFG, f, ensure_ascii=False, indent=2)
        return {"success": True}

    if action == "list_models":
        try:
            models = _chat_svc.list_models(
                api_key=command.get("api_key", ""),
                base_url=command.get("base_url", ""),
            )
            return {"success": True, "models": models}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    if action == "chat":
        messages = command.get("messages", [])
        connected_folder = command.get("connected_folder", "")
        _chat_svc.connected_folder = connected_folder
        try:
            reply, updated_messages = _chat_svc.chat(messages, _tool_executor)

            # 回退：如果 AI 没有调用任何工具（MiMo 等不支持 tool_use），
            # 检测用户消息中是否包含工作流意图，自动生成
            if not _chat_svc.tools_called and _contains_workflow_intent(messages):
                _log("FALLBACK: tool_use not called, auto-generating workflow from intent")
                _auto_generate_workflow(messages)

            return {"success": True, "reply": reply, "messages": updated_messages}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    if action == "execute_workflow":
        workflow_id = command.get("workflow_id", "")
        try:
            def _status_cb(step_id, status, message):
                _bridge.update_step_status_in_ui("", step_id, status, message)
            result = _engine.execute(workflow_id, status_callback=_status_cb)
            _log(f"execute_workflow: {workflow_id} -> overall_success={result.get('overall_success')}")

            # 自动将输出添加到地图
            if result.get("overall_success"):
                _auto_add_outputs_to_map(result)

            return {"success": True, "result": result}
        except Exception as exc:
            _log(f"execute_workflow error: {exc}")
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": f"未知 action: {action}"}


# Start chat pipe server in background thread
_chat_pipe_server = NamedPipeChatServer(_handle_chat_command)
_chat_pipe_server.start()


# =========================================================================
# Workflow tools
# =========================================================================

@mcp.tool()
def plan_workflow(
    goal: str,
    data_sources: list[dict],
    output_workspace: str = "",
) -> str:
    """
    根据目标描述和数据源，自动生成 GIS 分析步骤链。
    返回可视化步骤链 JSON，用户可修改参数后执行。

    goal: 分析目标，例如"分析城市热岛效应"
    data_sources: 数据源列表，每项包含 name/path/type(vector|raster|table|network)
    output_workspace: 输出工作空间路径（可留空）
    """
    wf_dict = _planner.plan(
        goal=goal,
        data_sources=data_sources,
        output_workspace=output_workspace,
    )
    _engine.load_workflow(wf_dict)
    if _bridge.is_pro_running():
        _bridge.push_workflow_to_ui(wf_dict)
    result = {
        "workflow": wf_dict,
        "message": (
            f"已生成工作流「{wf_dict['title']}」，共 {len(wf_dict['steps'])} 个步骤。"
            "可调用 execute_workflow 执行，或先用 modify_step_params 修改参数。"
        ),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def execute_workflow(
    workflow_id: str,
    from_step: int = 1,
    to_step: int = 0,
) -> str:
    """
    执行已生成的工作流步骤链。

    workflow_id: plan_workflow 返回的 workflow_id
    from_step: 从第几步开始执行，默认 1
    to_step: 执行到第几步，填 0 表示执行到末尾
    """
    result = _engine.execute(
        workflow_id=workflow_id,
        from_step=from_step,
        to_step=to_step if to_step > 0 else None,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def modify_step_params(
    workflow_id: str,
    step_id: int,
    params: dict,
    validate_only: bool = False,
) -> str:
    """
    修改工作流中某一步骤的参数。

    workflow_id: 工作流 ID
    step_id: 步骤编号
    params: 要更新的参数键值对
    validate_only: True 时只验证合法性，不保存修改
    """
    if validate_only:
        wf = _engine.get_workflow(workflow_id)
        if wf:
            step = wf.get_step(step_id)
            if step:
                import copy
                test_step = copy.deepcopy(step)
                test_step.params.update(params)
                schema = get_tool_schema(step.tool.replace("arcpy.", ""))
                from workflow.validator import WorkflowValidator
                errors = WorkflowValidator().validate_step_params(test_step, schema)
                result: Any = {"valid": len(errors) == 0, "errors": errors}
            else:
                result = {"error": f"步骤 {step_id} 不存在"}
        else:
            result = {"error": f"工作流 {workflow_id} 不存在"}
    else:
        result = _engine.update_step_params(workflow_id, step_id, params)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_workflow_status(workflow_id: str) -> str:
    """查询工作流状态和所有步骤的执行结果。"""
    wf = _engine.get_workflow(workflow_id)
    result = wf.to_dict() if wf else {"error": f"工作流 {workflow_id} 不存在"}
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_workflows() -> str:
    """列出当前会话中所有工作流。"""
    return json.dumps(_engine.list_workflows(), ensure_ascii=False, indent=2)


# =========================================================================
# Single tool execution
# =========================================================================

@mcp.tool()
def execute_single_tool(
    tool_path: str,
    params: dict = {},
    get_schema_only: bool = False,
) -> str:
    """
    直接执行单个 arcpy 工具。

    tool_path: 工具路径，如 "analysis.Buffer"、"sa.Slope"、"na.Solve"
    params: 工具参数字典
    get_schema_only: True 时只返回参数定义，不执行工具
    """
    if get_schema_only:
        return json.dumps(get_tool_schema(tool_path), ensure_ascii=False, indent=2)

    try:
        import arcpy  # type: ignore
        parts = tool_path.split(".")
        obj = arcpy
        for part in parts:
            obj = getattr(obj, part)
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        exec_result = obj(**clean)
        msgs: list[str] = []
        if hasattr(exec_result, "messageCount"):
            msgs = [exec_result.getMessage(i) for i in range(exec_result.messageCount)]
        result = {"success": True, "messages": msgs, "result": str(exec_result)}
    except ImportError:
        result = {"success": False, "error": "arcpy 未安装，请使用 arcgispro-py3 环境运行"}
    except Exception as exc:
        result = {"success": False, "error": str(exc)}

    return json.dumps(result, ensure_ascii=False, indent=2)


# =========================================================================
# Data inspection
# =========================================================================

@mcp.tool()
def describe_data(path: str) -> str:
    """描述数据源：字段、坐标系、要素类型、空间范围等。"""
    return json.dumps(_bridge.describe_data(path), ensure_ascii=False, indent=2)


@mcp.tool()
def list_workspace_data(workspace: str) -> str:
    """列出工作空间（文件夹或地理数据库）中的所有数据集。"""
    return json.dumps(_bridge.list_feature_classes(workspace), ensure_ascii=False, indent=2)


# =========================================================================
# Tool discovery
# =========================================================================

@mcp.tool()
def search_gis_tools(keyword: str) -> str:
    """按关键字搜索可用的 arcpy 工具，支持中文和英文，例如"缓冲区"、"slope"、"热点"。"""
    return json.dumps(search_tools(keyword), ensure_ascii=False, indent=2)


@mcp.tool()
def get_arcpy_tool_schema(tool_path: str) -> str:
    """
    获取指定 arcpy 工具的完整参数定义。
    tool_path 格式: "analysis.Buffer"、"sa.Slope" 等。
    """
    return json.dumps(get_tool_schema(tool_path), ensure_ascii=False, indent=2)


@mcp.tool()
def list_all_toolboxes() -> str:
    """列出所有可用的 ArcGIS Pro 工具箱及其模块名。"""
    return json.dumps(list_toolboxes(), ensure_ascii=False, indent=2)


# =========================================================================
# ArcGIS Pro UI / map control
# =========================================================================

@mcp.tool()
def get_map_info() -> str:
    """获取当前 ArcGIS Pro 工程中打开的地图和图层信息（需要 Pro 正在运行）。"""
    return json.dumps(arc_tools.get_current_map_info(), ensure_ascii=False, indent=2)


@mcp.tool()
def zoom_to_layer(layer_name: str) -> str:
    """在 ArcGIS Pro 中缩放到指定图层的范围。"""
    return json.dumps(_bridge.zoom_to_layer(layer_name), ensure_ascii=False, indent=2)


@mcp.tool()
def set_layer_visibility(layer_name: str, visible: bool) -> str:
    """显示或隐藏 ArcGIS Pro 中的图层。"""
    return json.dumps(_bridge.set_layer_visibility(layer_name, visible), ensure_ascii=False, indent=2)


@mcp.tool()
def add_layer_to_map(layer_path: str, map_name: str = "") -> str:
    """将数据文件添加到 ArcGIS Pro 当前地图。map_name 留空则添加到当前活动地图。"""
    return json.dumps(arc_tools.add_layer_to_map(layer_path, map_name), ensure_ascii=False, indent=2)


@mcp.tool()
def apply_symbology(
    layer_name: str,
    symbology_type: str,
    symbology_field: str = "",
    color_ramp: str = "Red-Yellow-Green",
    class_count: int = 5,
) -> str:
    """
    为 ArcGIS Pro 中的图层应用符号化样式。

    symbology_type: GRADUATED_COLORS | GRADUATED_SYMBOLS | UNIQUE_VALUES | SINGLE_SYMBOL | HEAT_MAP
    symbology_field: 用于分级的字段名
    color_ramp: 色带名称
    class_count: 分类数量
    """
    return json.dumps(
        arc_tools.apply_symbology(layer_name, symbology_type, symbology_field, color_ramp, class_count),
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
def export_map(
    output_path: str,
    map_name: str = "",
    layout_name: str = "",
    resolution: int = 300,
) -> str:
    """
    将当前地图或布局导出为 PDF 或 PNG。

    output_path: 输出路径，以 .pdf 或 .png 结尾
    layout_name: 布局名称（有布局时优先使用布局）
    resolution: 分辨率 DPI，默认 300
    """
    if output_path.lower().endswith(".png"):
        result = arc_tools.export_map_to_png(output_path, map_name=map_name, resolution=resolution)
    else:
        result = arc_tools.export_map_to_pdf(output_path, map_name=map_name, layout_name=layout_name, resolution=resolution)
    return json.dumps(result, ensure_ascii=False, indent=2)


# =========================================================================
# Environment
# =========================================================================

@mcp.tool()
def get_arcpy_env() -> str:
    """获取当前 arcpy 环境设置（工作空间、坐标系、栅格分辨率等）。"""
    return json.dumps(_bridge.get_arcpy_env(), ensure_ascii=False, indent=2)


@mcp.tool()
def set_arcpy_env(
    workspace: str = "",
    overwrite_output: bool = True,
    cell_size: float = 0,
    output_coordinate_system: str = "",
    extent: str = "",
) -> str:
    """
    设置 arcpy 环境变量，影响后续所有工具的执行。

    workspace: 默认工作空间路径
    overwrite_output: 是否允许覆盖已有输出，默认 True
    cell_size: 栅格默认分辨率
    output_coordinate_system: 输出坐标系（WKID 或名称）
    extent: 分析范围（"xmin ymin xmax ymax" 格式）
    """
    settings: dict[str, Any] = {}
    if workspace:
        settings["workspace"] = workspace
    settings["overwriteOutput"] = overwrite_output
    if cell_size > 0:
        settings["cellSize"] = cell_size
    if output_coordinate_system:
        settings["outputCoordinateSystem"] = output_coordinate_system
    if extent:
        settings["extent"] = extent
    return json.dumps(_bridge.set_arcpy_env(settings), ensure_ascii=False, indent=2)


@mcp.tool()
def check_extensions() -> str:
    """检查 ArcGIS Pro 扩展许可状态（Spatial Analyst、Network Analyst 等）。"""
    return json.dumps(_bridge.check_extensions(), ensure_ascii=False, indent=2)


# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    import sys
    print("ArcGIS Pro MCP Server 已启动，等待 MCP 客户端连接...", file=sys.stderr, flush=True)
    print("（此窗口正常运行中，无需关闭。若要停止，按 Ctrl+C）", file=sys.stderr, flush=True)
    print("-" * 50, file=sys.stderr, flush=True)
    mcp.run(transport="stdio")
