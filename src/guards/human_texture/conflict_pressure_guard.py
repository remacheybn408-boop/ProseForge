"""conflict_pressure_guard.py — 剧情阻力检测 v0.6.6"""
import re

def run_conflict_check(content: str, chapter_no: int = 0) -> dict:
    findings = []
    score = 100

    # 检测是否有明确阻碍
    obstacle_markers = ["但", "可是", "然而", "却被", "拦", "阻", "挡", "拒绝", "不让", "不行",
                        "扣", "罚", "警告", "危险", "小心", "来不及", "晚了"]
    obstacle_count = sum(1 for m in obstacle_markers if m in content)

    if obstacle_count < 3:
        findings.append({"level": "WARN", "message": f"章节阻力标记过少 ({obstacle_count})", "suggestion": "添加外部阻碍、冲突或被迫选择"})
        score -= 20

    # 检测是否有具体行动
    action_markers = ["站起来", "推开门", "走过去", "拿起", "放下", "蹲下", "转身", "抓住",
                      "跑", "冲", "走", "跳", "爬", "捡", "握"]
    action_count = sum(1 for m in action_markers if m in content)
    if action_count < 5:
        findings.append({"level": "WARN", "message": f"具体行动过少 ({action_count})", "suggestion": "人物需要通过行动推动剧情，不只是思考和对话"})
        score -= 15

    # 检测章末钩子（最后500字）
    tail = content[-500:] if len(content) > 500 else content
    hook_markers = ["没有", "还没", "即将", "不知道", "等待", "明天", "接下来", "怎么办",
                    "发现", "突然", "变了", "不对", "难道"]
    hook_count = sum(1 for m in hook_markers if m in tail)
    if hook_count < 2:
        findings.append({"level": "WARN", "message": "章末钩子不足", "suggestion": "结尾留下悬念、未解决的问题或新的压力"})
        score -= 15

    # 检测状态变化
    change_markers = ["变了", "不同了", "已经不再是", "终于", "再也不是", "成为", "发现"]
    change_count = sum(1 for m in change_markers if m in content)
    if change_count < 1:
        findings.append({"level": "INFO", "message": "未检测到明确的状态变化", "suggestion": "章末人物状态应与章初有所不同"})
        score -= 5

    status = "PASS" if score >= 70 else ("WARNING" if score >= 55 else "FAIL")
    return {"guard": "conflict_pressure_guard", "status": status, "score": max(0, score), "findings": findings, "chapter_no": chapter_no}
