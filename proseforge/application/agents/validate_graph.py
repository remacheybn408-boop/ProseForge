from proseforge.domain.agents.task_graph import TaskGraph
from proseforge.domain.agents.roles import AgentRole

def validate_graph(graph: TaskGraph) -> tuple[str, ...]:
    if len(graph.tasks) > 64: raise ValueError("task graph exceeds node limit")
    if len({task.id for task in graph.tasks}) != len(graph.tasks): raise ValueError("duplicate task id")
    for task in graph.tasks:
        if task.role not in {role.value for role in AgentRole}: raise ValueError("unknown role")
        if task.token_budget <= 0: raise ValueError("task token budget must be positive")
        if len(task.depends_on) > 8: raise ValueError("task fan-in exceeds limit")
    order = graph.topological_order()
    if max((len(task.depends_on) for task in graph.tasks), default=0) > 8: raise ValueError("task fanout exceeds limit")
    return order
