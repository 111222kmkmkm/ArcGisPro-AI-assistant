from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class DataSource:
    name: str
    path: str
    type: str  # vector | raster | table | network | geodatabase


@dataclass
class WorkflowStep:
    step_id: int
    name: str
    tool: str                        # e.g. "arcpy.analysis.Buffer"
    description: str
    params: dict[str, Any]
    editable_params: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    error_message: str = ""
    estimated_duration: str = ""
    result_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "tool": self.tool,
            "description": self.description,
            "params": self.params,
            "editable_params": self.editable_params,
            "depends_on": self.depends_on,
            "outputs": self.outputs,
            "status": self.status.value,
            "error_message": self.error_message,
            "estimated_duration": self.estimated_duration,
            "result_messages": self.result_messages,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WorkflowStep:
        d = d.copy()
        d["status"] = StepStatus(d.get("status", "pending"))
        return cls(**d)


@dataclass
class Workflow:
    workflow_id: str
    title: str
    description: str
    data_sources: list[DataSource]
    steps: list[WorkflowStep]
    output_workspace: str = ""
    created_at: str = ""

    def get_step(self, step_id: int) -> WorkflowStep | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "description": self.description,
            "data_sources": [
                {"name": ds.name, "path": ds.path, "type": ds.type}
                for ds in self.data_sources
            ],
            "steps": [s.to_dict() for s in self.steps],
            "output_workspace": self.output_workspace,
            "created_at": self.created_at,
        }
