from proseforge.domain.agents.task_graph import AgentTaskSpec, TaskGraph
from proseforge.application.agents.validate_graph import validate_graph

def expand_graph(graph: TaskGraph, parent_task_id: str, task: AgentTaskSpec, reason: str) -> TaskGraph:
    if not reason.strip(): raise ValueError("expansion reason is required")
    if parent_task_id not in {item.id for item in graph.tasks}: raise ValueError("parent task not found")
    if task.id in {item.id for item in graph.tasks}: raise ValueError("duplicate expansion")
    expanded = TaskGraph(graph.revision + 1, graph.tasks + (task,)); validate_graph(expanded); return expanded
