"""prompt_specificity_guard.py — 提示词具体度检测 v0.6.6"""
import re

CHECK_FIELDS = [
    ("章节目标", ["目标", "本章写", "本章讲", "本章需要", "目的是"]),
    ("具体阻碍", ["阻碍", "阻止", "冲突", "阻力", "矛盾", "问题"]),
    ("具体物件", ["物件", "物品", "道具", "钥匙", "信", "纸条"]),
    ("角色声纹", ["声纹", "口吻", "语气", "方言", "说话方式"]),
    ("章末钩子", ["钩子", "结尾", "悬念", "结尾钩子", "下一章"]),
    ("禁用句式", ["禁用", "禁止", "避免", "不要用"]),
    ("承接要求", ["承接", "上章", "前文", "上一章", "延续"]),
]

def run_prompt_check(task_card: str, chapter_no: int = 0) -> dict:
    """检查任务卡的具体度。需传入 task card 文本。"""
    findings = []
    score = 100
    found_count = 0

    for field, keywords in CHECK_FIELDS:
        found = any(kw in task_card for kw in keywords)
        if found:
            found_count += 1
        else:
            findings.append({"level": "WARN", "message": f"缺少「{field}」描述", "suggestion": f"在任务卡中明确本章的{field}"})
            score -= 15

    status = "PASS" if score >= 80 else ("WARNING" if score >= 60 else "FAIL")
    return {"guard": "prompt_specificity_guard", "status": status, "score": max(0, score), "findings": findings, "chapter_no": chapter_no}
