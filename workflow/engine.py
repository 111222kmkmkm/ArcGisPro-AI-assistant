from __future__ import annotations
import json
import re
from typing import Any
from .step import Workflow, WorkflowStep, WorkflowStep, DataSource, StepStatus
from .validator import WorkflowValidator


_REF_WS = re.compile(r"\$\{workspace\}/(.+)")
_REF_DS = re.compile(r"\$\{data_sources\.([^}]+)\}")
_REF_OUT = re.compile(r"\$\{outputs\.([^}]+)\}")


class WorkflowEngine:
    def __init__(self) -> None:
        self._sessions: dict[str, Workflow] = {}
        self._validator = WorkflowValidator()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def load_workflow(self, wf_dict: dict) -> Workflow:
        sources = [DataSource(**ds) for ds in wf_dict["data_sources"]]
        steps = [WorkflowStep.from_dict(s) for s in wf_dict["steps"]]
        wf = Workflow(
            workflow_id=wf_dict["workflow_id"],
            title=wf_dict["title"],
            description=wf_dict["description"],
            data_sources=sources,
            steps=steps,
            output_workspace=wf_dict.get("output_workspace", ""),
            created_at=wf_dict.get("created_at", ""),
        )
        self._sessions[wf.workflow_id] = wf
        return wf

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return self._sessions.get(workflow_id)

    def list_workflows(self) -> list[dict]:
        return [
            {
                "workflow_id": wf.workflow_id,
                "title": wf.title,
                "steps": len(wf.steps),
                "status": self._overall_status(wf),
            }
            for wf in self._sessions.values()
        ]

    def update_step_params(
        self,
        workflow_id: str,
        step_id: int,
        params: dict[str, Any],
    ) -> dict:
        wf = self._sessions.get(workflow_id)
        if wf is None:
            return {"success": False, "error": f"工作流 {workflow_id} 不存在"}
        step = wf.get_step(step_id)
        if step is None:
            return {"success": False, "error": f"步骤 {step_id} 不存在"}
        step.params.update(params)
        return {"success": True, "step": step.to_dict()}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        workflow_id: str,
        from_step: int = 1,
        to_step: int | None = None,
        status_callback=None,  # callback(step_id, status, message)
    ) -> dict:
        wf = self._sessions.get(workflow_id)
        if wf is None:
            return {"success": False, "error": f"工作流 {workflow_id} 不存在"}

        errors = self._validator.validate(wf)
        if errors:
            return {"success": False, "validation_errors": errors}

        results: list[dict] = []
        outputs: dict[str, str] = {}

        for step in wf.steps:
            if step.step_id < from_step:
                continue
            if to_step is not None and step.step_id > to_step:
                break

            # check dependencies
            for dep_id in step.depends_on:
                dep = wf.get_step(dep_id)
                if dep and dep.status != StepStatus.COMPLETED:
                    step.status = StepStatus.ERROR
                    step.error_message = f"依赖步骤 {dep_id} 未完成"
                    if status_callback:
                        status_callback(step.step_id, "error", step.error_message)
                    results.append({"step_id": step.step_id, "success": False, "error": step.error_message})
                    continue

            step.status = StepStatus.RUNNING
            if status_callback:
                status_callback(step.step_id, "running", "")
            resolved_params = self._resolve_params(step.params, wf, outputs)

            result = self._run_step(step, resolved_params)
            if result["success"]:
                step.status = StepStatus.COMPLETED
                step.result_messages = result.get("messages", [])
                if status_callback:
                    status_callback(step.step_id, "completed", "")
                for out_name in step.outputs:
                    if out_name in resolved_params.values():
                        outputs[out_name] = str(list(resolved_params.values())[0])
                    else:
                        outputs[out_name] = resolved_params.get("out_feature_class") or resolved_params.get("out_raster") or ""
            else:
                step.status = StepStatus.ERROR
                step.error_message = result.get("error", "未知错误")
                if status_callback:
                    status_callback(step.step_id, "error", step.error_message)

            results.append({
                "step_id": step.step_id,
                "name": step.name,
                "success": result["success"],
                "messages": result.get("messages", []),
                "error": result.get("error", ""),
            })

            if not result["success"]:
                break  # stop on first error

        return {
            "workflow_id": workflow_id,
            "overall_success": all(r["success"] for r in results),
            "steps_executed": len(results),
            "results": results,
            "workflow": wf.to_dict(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_params(
        self,
        params: dict[str, Any],
        wf: Workflow,
        outputs: dict[str, str],
    ) -> dict[str, Any]:
        ds_map = {ds.name: ds.path for ds in wf.data_sources}
        resolved: dict[str, Any] = {}

        for key, val in params.items():
            if not isinstance(val, str):
                resolved[key] = val
                continue

            def _sub_ds(m: re.Match) -> str:
                return ds_map.get(m.group(1), m.group(0))

            def _sub_ws(m: re.Match) -> str:
                base = wf.output_workspace or "memory"
                return f"{base}/{m.group(1)}"

            def _sub_out(m: re.Match) -> str:
                return outputs.get(m.group(1), m.group(0))

            val = _REF_DS.sub(_sub_ds, val)
            val = _REF_WS.sub(_sub_ws, val)
            val = _REF_OUT.sub(_sub_out, val)
            resolved[key] = val

        return resolved

    def _run_step(self, step: WorkflowStep, params: dict[str, Any]) -> dict:
        try:
            import arcpy  # type: ignore
        except ImportError:
            return {
                "success": False,
                "error": "arcpy 未安装或环境不正确，请使用 arcgispro-py3 环境运行",
            }

        try:
            # resolve tool reference: "arcpy.analysis.Buffer" → arcpy.analysis.Buffer
            parts = step.tool.split(".")
            obj = arcpy
            for part in parts[1:]:
                obj = getattr(obj, part)

            # filter out None-valued optional params
            clean_params = {k: v for k, v in params.items() if v is not None}
            result = obj(**clean_params)

            messages = []
            if hasattr(result, "messageCount"):
                messages = [result.getMessage(i) for i in range(result.messageCount)]

            return {"success": True, "messages": messages}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _overall_status(self, wf: Workflow) -> str:
        statuses = {s.status for s in wf.steps}
        if StepStatus.ERROR in statuses:
            return "error"
        if StepStatus.RUNNING in statuses:
            return "running"
        if all(s.status == StepStatus.COMPLETED for s in wf.steps):
            return "completed"
        return "pending"
