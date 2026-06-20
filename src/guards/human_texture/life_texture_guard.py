"""life_texture_guard.py — 生活毛边检测 v0.6.6"""
import re

CONCRETE_OBJECTS = [
    "伞", "钥匙", "手机", "碗", "杯", "刀", "斧", "铁锹", "麻绳", "纸", "笔",
    "炭", "石", "砖", "瓦", "布", "鞋", "帽", "袋", "绳", "锁", "灯", "烛",
    "扇", "炉", "锅", "勺", "筷", "瓶", "罐", "盒", "箱", "柜", "架", "床",
    "席", "被", "枕", "巾", "帕", "盆", "桶", "瓢", "扫帚", "柴", "炭",
]

ABSTRACT_ATMOSPHERE = [
    "雨声", "灯光", "风铃", "咖啡香", "沉默", "眼神", "微笑", "夜色",
    "暖黄色", "窗外", "咖啡", "拿铁", "雾气", "黄昏", "晚霞",
]

def run_life_texture_check(content: str, chapter_no: int = 0) -> dict:
    findings = []
    score = 100

    # 具体物件计数
    obj_count = 0
    obj_found = set()
    for obj in CONCRETE_OBJECTS:
        if obj in content:
            obj_count += content.count(obj)
            obj_found.add(obj)

    if obj_count < 5:
        findings.append({"level": "WARN", "message": f"具体物件过少 ({obj_count}处)", "suggestion": "增加生活物件细节，让场景更具体"})
        score -= 20
    elif obj_count < 10:
        findings.append({"level": "INFO", "message": f"具体物件 {obj_count}处", "suggestion": "物件可以更多参与剧情"})
        score -= 10

    # 抽象氛围词检查
    atm_count = 0
    for atm in ABSTRACT_ATMOSPHERE:
        if atm in content:
            atm_count += content.count(atm)

    if atm_count > obj_count and obj_count > 0:
        findings.append({"level": "INFO", "message": f"抽象氛围词 ({atm_count}) 多于具体物件 ({obj_count})", "suggestion": "减少泛用氛围描写，增加具体生活细节"})
        score -= 10

    status = "PASS" if score >= 70 else ("WARNING" if score >= 55 else "FAIL")
    return {"guard": "life_texture_guard", "status": status, "score": max(0, score), "findings": findings, "chapter_no": chapter_no}
