"""
AI Chat Service — 调用 Claude API，支持 tool_use 直接执行 arcpy 工具。
被 named_pipe_server.py 调用，运行在 Python MCP Server 进程内。
"""
from __future__ import annotations
import json
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


# Claude tools schema：把核心 arcpy 操作暴露给 AI
_TOOLS: list[dict] = [
    {
        "name": "plan_workflow",
        "description": "生成 GIS 分析工作流步骤链并推送到 ArcGIS Pro 工作流面板。必须先调用此工具生成工作流，再调用 execute_workflow 执行。",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "分析目标描述"},
                "data_sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "path": {"type": "string"},
                            "type": {"type": "string", "enum": ["vector", "raster", "table", "network"]},
                        },
                        "required": ["name", "path", "type"],
                    },
                },
                "output_workspace": {"type": "string"},
                "steps": {
                    "type": "array",
                    "description": "自定义工作流步骤列表。如果不提供，将根据 goal 自动匹配模板。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "步骤名称"},
                            "tool": {"type": "string", "description": "arcpy 工具路径，如 analysis.Buffer、management.SelectLayerByAttribute"},
                            "description": {"type": "string", "description": "步骤说明"},
                            "params": {"type": "object", "description": "工具参数字典"},
                        },
                        "required": ["name", "tool", "params"],
                    },
                },
            },
            "required": ["goal", "data_sources"],
        },
    },
    {
        "name": "execute_workflow",
        "description": "执行已生成的工作流步骤链",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "from_step": {"type": "integer", "default": 1},
                "to_step": {"type": "integer", "default": 0},
            },
            "required": ["workflow_id"],
        },
    },
    {
        "name": "execute_single_tool",
        "description": "直接执行单个 arcpy 工具，例如缓冲区、裁剪、坡度分析等",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_path": {
                    "type": "string",
                    "description": "工具路径，如 analysis.Buffer、sa.Slope、na.Solve",
                },
                "params": {
                    "type": "object",
                    "description": "工具参数字典",
                },
            },
            "required": ["tool_path", "params"],
        },
    },
    {
        "name": "describe_data",
        "description": "查看数据源的字段、坐标系、范围等信息",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_workspace_data",
        "description": "列出工作空间中的所有数据集（要素类、栅格、表）",
        "input_schema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
            "required": ["workspace"],
        },
    },
    {
        "name": "search_gis_tools",
        "description": "搜索可用的 arcpy 工具，支持中英文关键字",
        "input_schema": {
            "type": "object",
            "properties": {"keyword": {"type": "string"}},
            "required": ["keyword"],
        },
    },
    {
        "name": "zoom_to_layer",
        "description": "在 ArcGIS Pro 中缩放到指定图层",
        "input_schema": {
            "type": "object",
            "properties": {"layer_name": {"type": "string"}},
            "required": ["layer_name"],
        },
    },
    {
        "name": "set_layer_visibility",
        "description": "显示或隐藏 ArcGIS Pro 中的图层",
        "input_schema": {
            "type": "object",
            "properties": {
                "layer_name": {"type": "string"},
                "visible": {"type": "boolean"},
            },
            "required": ["layer_name", "visible"],
        },
    },
    {
        "name": "get_map_info",
        "description": "获取当前地图和图层列表",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_arcpy_env",
        "description": "设置 arcpy 环境（工作空间、坐标系等）",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "overwrite_output": {"type": "boolean"},
                "cell_size": {"type": "number"},
                "output_coordinate_system": {"type": "string"},
            },
        },
    },
]

_SYSTEM_PROMPT_ZH = """你是一个深度集成在 ArcGIS Pro 中的 GIS 专家 AI 助手。

你可以：
- 理解用户的地理空间分析需求，自动规划分析流程
- 调用 arcpy 工具执行空间分析、数据管理、网络分析、栅格分析等
- 生成可视化步骤链并推送到 ArcGIS Pro 工作流面板
- 控制 ArcGIS Pro 界面（缩放图层、切换可见性等）

{workspace_info}

**核心工作流规则（必须严格遵守）：**
当用户要求执行分析任务时，你必须按以下顺序操作：
1. 第一步：调用 plan_workflow 生成完整的工作流步骤链（包含所有步骤），工作流会自动显示在 ArcGIS Pro 工作流面板中
2. 第二步：调用 execute_workflow 执行该工作流
3. 绝对不要直接调用 execute_single_tool，必须先用 plan_workflow 生成工作流

**错误自动处理规则（必须遵守）：**
当 execute_workflow 或 execute_single_tool 执行失败时：
1. 仔细分析错误信息，找出失败原因（参数错误、路径不存在、工具名称错误、字段不存在等）
2. 自动修正错误：重新调用 plan_workflow 生成修正后的工作流，或直接用正确的参数重新执行
3. 最多重试 5 次，每次都要根据错误信息调整方案
4. 只有在 5 次尝试仍然失败后，才向用户报告错误并详细解释所有尝试过的方法和最终失败原因
5. 绝对不要在第一次失败就放弃，必须尝试自行解决

回复规则：
- 回复使用中文
- 执行工具后，用简洁的语言说明执行结果
- 生成步骤链时，简要说明每步的作用
- 遇到错误时，自动修复并重试，不要直接报错给用户
- 不要重复展示工具返回的原始 JSON，用自然语言总结即可
- 当用户只输入数据名称时，在当前工作空间中自动查找匹配的数据集"""

_SYSTEM_PROMPT_EN = """You are a GIS expert AI assistant deeply integrated into ArcGIS Pro.

You can:
- Understand the user's geospatial analysis needs and plan analysis workflows automatically
- Call arcpy tools to run spatial analysis, data management, network analysis, raster analysis, etc.
- Generate visual step chains and push them to the ArcGIS Pro workflow pane
- Control the ArcGIS Pro UI (zoom to layers, toggle visibility, etc.)

{workspace_info}

**Core Workflow Rules (MUST follow strictly):**
When the user requests an analysis task, you MUST:
1. Step 1: Call plan_workflow to generate a complete workflow (with all steps). The workflow will be displayed in the ArcGIS Pro workflow panel.
2. Step 2: Call execute_workflow to execute the workflow.
3. NEVER call execute_single_tool directly. Always use plan_workflow first.

**Error Auto-Handling Rules (MUST follow):**
When execute_workflow or execute_single_tool fails:
1. Analyze the error message carefully to find the root cause (wrong parameters, missing path, incorrect tool name, missing field, etc.)
2. Automatically fix the error: re-call plan_workflow with corrected workflow, or re-execute with correct parameters
3. Retry up to 5 times, adjusting based on error info each time
4. Only report to the user after 5 attempts still fail, explaining all attempts and the final error reason
5. NEVER give up on the first error - always try to fix it yourself

Reply rules:
- Reply in English
- After running a tool, summarize the result concisely
- When generating a step chain, briefly explain what each step does
- On errors, explain the cause and suggest a fix
- Do not echo raw JSON returned by tools; summarize in natural language
- When the user only inputs a data name, automatically search for matching datasets in the current workspace"""


def _system_prompt(language: str, connected_folder: str = "") -> str:
    workspace_info = _get_workspace_info(connected_folder)
    tpl = _SYSTEM_PROMPT_EN if language == "en" else _SYSTEM_PROMPT_ZH
    return tpl.format(workspace_info=workspace_info)


def _get_workspace_info(connected_folder: str = "") -> str:
    """获取当前 ArcGIS Pro 工作空间、地图图层和连接文件夹信息，注入到系统提示中。"""
    try:
        import arcpy  # type: ignore
        lines = []

        # 1. 工作空间数据
        ws = arcpy.env.workspace or ""
        if ws:
            fcs = arcpy.ListFeatureClasses() or []
            rasters = arcpy.ListRasters() or []
            tables = arcpy.ListTables() or []
            lines.append(f"当前工作空间：{ws}")
            if fcs:
                lines.append(f"  要素类 ({len(fcs)}): {', '.join(fcs[:20])}")
            if rasters:
                lines.append(f"  栅格 ({len(rasters)}): {', '.join(rasters[:20])}")
            if tables:
                lines.append(f"  表 ({len(tables)}): {', '.join(tables[:20])}")
        else:
            lines.append("当前工作空间：未设置")

        # 2. 内容窗格（当前地图图层）
        try:
            import arcpy.mp as mp  # type: ignore
            aprx = mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if active_map:
                layers = active_map.listLayers()
                tables_in_map = active_map.listTables()
                if layers:
                    layer_lines = []
                    for lyr in layers:
                        desc = f"{lyr.name}"
                        if lyr.isFeatureLayer:
                            desc += " (要素图层)"
                        elif lyr.isRasterLayer:
                            desc += " (栅格图层)"
                        elif lyr.isGroupLayer:
                            desc += " (组)"
                        if lyr.dataSource:
                            desc += f" → {lyr.dataSource}"
                        layer_lines.append(f"    {desc}")
                    lines.append(f"\n内容窗格 - 当前地图 ({active_map.name})，共 {len(layers)} 个图层：")
                    lines.extend(layer_lines)
                if tables_in_map:
                    lines.append(f"  地图表 ({len(tables_in_map)}): {', '.join(t.name for t in tables_in_map)}")
                if not layers and not tables_in_map:
                    lines.append(f"\n内容窗格 - 当前地图 ({active_map.name})：无图层")
        except Exception:
            lines.append("\n内容窗格：无法获取")

        # 3. 连接文件夹
        if connected_folder:
            try:
                import os
                if os.path.isdir(connected_folder):
                    files = os.listdir(connected_folder)
                    # 分类文件
                    shp_files = [f for f in files if f.lower().endswith('.shp')]
                    tif_files = [f for f in files if f.lower().endswith(('.tif', '.tiff'))]
                    gdb_dirs = [f for f in files if f.lower().endswith('.gdb')]
                    csv_files = [f for f in files if f.lower().endswith('.csv')]
                    other = [f for f in files if f not in shp_files + tif_files + gdb_dirs + csv_files
                             and not f.startswith('.') and os.path.isfile(os.path.join(connected_folder, f))]
                    lines.append(f"\n连接文件夹：{connected_folder}")
                    if shp_files:
                        lines.append(f"  矢量数据 ({len(shp_files)}): {', '.join(shp_files[:20])}")
                    if tif_files:
                        lines.append(f"  栅格数据 ({len(tif_files)}): {', '.join(tif_files[:20])}")
                    if gdb_dirs:
                        lines.append(f"  地理数据库 ({len(gdb_dirs)}): {', '.join(gdb_dirs)}")
                    if csv_files:
                        lines.append(f"  CSV ({len(csv_files)}): {', '.join(csv_files[:20])}")
                    if not (shp_files or tif_files or gdb_dirs or csv_files):
                        lines.append(f"  文件 ({len(other)}): {', '.join(other[:20])}")
                    lines.append(f"  完整路径示例：{os.path.join(connected_folder, '<文件名>')}")
            except Exception:
                lines.append(f"\n连接文件夹：{connected_folder}（无法读取内容）")

        lines.append("\n规则：当用户提到数据名称时，按以下优先级匹配：1) 内容窗格图层名 2) 连接文件夹中的文件 3) 工作空间数据。匹配到后自动使用完整路径。")
        return "\n".join(lines)
    except Exception:
        return "当前工作空间和内容窗格：无法获取。请确保 ArcGIS Pro 已打开项目。"


class AIChatService:
    def __init__(self) -> None:
        self._client = None
        self._model = "claude-sonnet-4-6"
        self._api_key: str = ""
        self._base_url: str = ""
        self._language: str = "zh"
        self.tools_called = False  # 最近一次 chat 是否调用了工具
        self.connected_folder: str = ""  # 用户连接的文件夹路径

    def configure(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        base_url: str = "",
        language: str = "zh",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or ""
        self._language = language or "zh"
        self._client = None  # reset so next call re-initializes

    def _new_client(self):
        import anthropic  # type: ignore
        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return anthropic.Anthropic(**kwargs)

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # type: ignore  # noqa: F401
            except ImportError:
                raise RuntimeError("anthropic 未安装，请运行: pip install anthropic")
            if not self._api_key:
                raise RuntimeError("未配置 API Key，请在 ArcGIS Pro AI 设置中填写 Anthropic API Key")
            self._client = self._new_client()
        return self._client

    def list_models(
        self,
        api_key: str = "",
        base_url: str = "",
    ) -> list[str]:
        """获取可用模型列表。允许临时传入 key/url（设置界面点击"获取"时还没保存）。"""
        try:
            import anthropic  # type: ignore
        except ImportError:
            raise RuntimeError("anthropic 未安装，请运行: pip install anthropic")

        key = api_key or self._api_key
        if not key:
            raise RuntimeError("请先填写 API Key")

        kwargs: dict[str, Any] = {"api_key": key}
        url = base_url or self._base_url
        if url:
            kwargs["base_url"] = url
        client = anthropic.Anthropic(**kwargs)

        ids: list[str] = []
        try:
            page = client.models.list(limit=100)
            for m in page.data:
                mid = getattr(m, "id", None)
                if mid:
                    ids.append(mid)
        except Exception:
            # 部分 API 提供商不支持 /v1/models，根据 URL 返回常用模型列表
            if url and "mimo" in url.lower():
                ids = ["mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-flash"]
            else:
                ids = [
                    "claude-sonnet-4-6",
                    "claude-opus-4-7",
                    "claude-haiku-4-5-20251001",
                ]
        return ids

    def chat(
        self,
        messages: list[dict],
        tool_executor,  # callable(tool_name, tool_input) -> str
    ) -> tuple[str, list[dict]]:
        """
        发送消息历史给 Claude，处理 tool_use 循环直到获得最终文本回复。
        返回 (最终文字回复, 更新后的消息历史)
        """
        client = self._get_client()
        system_prompt = _system_prompt(self._language, self.connected_folder)

        self.tools_called = False

        # 保护：每次 tool_use 循环最多 15 轮，避免死循环
        for round_i in range(15):
            _log(f"CHAT round {round_i}: model={self._model}, messages={len(messages)}")
            response = client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                tools=_TOOLS,
                messages=messages,
            )
            _log(f"  response: stop_reason={response.stop_reason}, blocks={len(response.content)}")

            # 将 assistant 回复追加到历史
            assistant_content = [block.model_dump() for block in response.content]
            messages = messages + [{"role": "assistant", "content": assistant_content}]

            if response.stop_reason == "end_turn":
                # 提取最终文字
                text = next(
                    (b["text"] for b in assistant_content if b.get("type") == "text"),
                    "",
                )
                _log(f"  end_turn: text={text[:200]}")
                return text, messages

            if response.stop_reason == "tool_use":
                self.tools_called = True
                tool_results = []
                for block in assistant_content:
                    if block.get("type") != "tool_use":
                        continue
                    tool_name = block["name"]
                    tool_input = block["input"]
                    tool_use_id = block["id"]
                    _log(f"  tool_use: {tool_name} id={tool_use_id}")

                    try:
                        result_str = tool_executor(tool_name, tool_input)
                    except Exception as exc:
                        result_str = json.dumps({"error": str(exc)}, ensure_ascii=False)
                        _log(f"  tool_error: {exc}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_str,
                    })

                messages = messages + [{"role": "user", "content": tool_results}]
                continue

            # max_tokens 或其他停止原因
            _log(f"  unexpected stop_reason: {response.stop_reason}")
            break

        # 轮次用完，强制请求一次纯文字回复（不带 tools）
        _log(f"  max rounds reached, requesting final text response")
        try:
            final_resp = client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt + "\n\n重要：请用自然语言总结已完成的操作和结果，不要输出任何工具调用格式。",
                messages=messages,
            )
            final_content = [block.model_dump() for block in final_resp.content]
            text = next(
                (b["text"] for b in final_content if b.get("type") == "text"),
                "",
            )
            # 清理可能残留的工具调用 XML 标记
            import re
            text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text)
            text = re.sub(r"<function-[^>]*>[\s\S]*?</function-[^>]*>", "", text)
            text = text.strip()
            if not text:
                text = "已执行多个工具操作，请查看工作流面板中的步骤状态。"
            return text, messages
        except Exception:
            return "已执行多个工具操作，请查看工作流面板中的步骤状态。", messages
