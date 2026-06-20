"""adapters — 把各 detector 的原始输出归一化为 list[Finding]。

约定：每个 adapter 文件暴露一个函数 `adapt(detector_output: dict, *, text: str) -> list[Finding]`。
不修改 detector 自身代码。
"""
from .anti_ai import adapt as adapt_anti_ai  # noqa: F401
