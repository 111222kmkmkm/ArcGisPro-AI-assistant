from __future__ import annotations
import re
from typing import Any
from .step import Workflow, WorkflowStep, DataSource


_PARAM_REF = re.compile(r"\$\{([^}]+)\}")


class WorkflowValidator:
    def validate(self, workflow: Workflow) -> list[str]:
        errors: list[str] = []
        step_ids = {s.step_id for s in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"步骤 {step.step_id} 依赖不存在的步骤 {dep}"
                    )
            self._check_cycles(step, workflow, [], errors)
            self._resolve_param_refs(step, workflow, errors)

        return errors

    def _check_cycles(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        visited: list[int],
        errors: list[str],
    ) -> None:
        if step.step_id in visited:
            errors.append(f"步骤链中存在循环依赖，涉及步骤 {step.step_id}")
            return
        for dep_id in step.depends_on:
            dep = workflow.get_step(dep_id)
            if dep:
                self._check_cycles(dep, workflow, visited + [step.step_id], errors)

    def _resolve_param_refs(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        errors: list[str],
    ) -> None:
        ds_names = {ds.name for ds in workflow.data_sources}
        for key, val in step.params.items():
            if not isinstance(val, str):
                continue
            for ref in _PARAM_REF.findall(val):
                parts = ref.split(".")
                if parts[0] == "data_sources":
                    if len(parts) < 2 or parts[1] not in ds_names:
                        errors.append(
                            f"步骤 {step.step_id} 参数 '{key}' 引用了不存在的数据源 '{ref}'"
                        )
                elif parts[0] == "workspace":
                    pass  # resolved at runtime
                else:
                    pass  # output references resolved at runtime

    def validate_step_params(
        self, step: WorkflowStep, schema: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        for param_def in schema.get("parameters", []):
            name = param_def["name"]
            if param_def.get("required") and param_def.get("direction") == "Input":
                if name not in step.params or step.params[name] in ("", None, "#"):
                    errors.append(f"必填参数 '{param_def['display_name']}' 未填写")
        return errors
