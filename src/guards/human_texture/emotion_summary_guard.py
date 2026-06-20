"""emotion_summary_guard.py — 情绪总结检测 v0.6.6"""
import re

ABSTRACT_EMOTIONS = ["复杂", "说不上来", "某种感觉", "仿佛", "终于明白", "无法形容",
                     "心里一沉", "空气安静", "沉默蔓延", "情绪翻涌", "眼眶发热",
                     "喉咙发紧", "说不出是什么滋味", "心里有什么东西"]

def run_emotion_summary_check(content: str, chapter_no: int = 0) -> dict:
    findings = []
    total_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    if total_chars == 0:
        return {"guard": "emotion_summary_guard", "status": "PASS", "score": 100, "findings": []}

    count = 0
    for phrase in ABSTRACT_EMOTIONS:
        matches = re.findall(phrase, content)
        if matches:
            count += len(matches)
            if len(matches) > 1:
                findings.append({"level": "WARN", "message": f"「{phrase}」出现 {len(matches)} 次", "suggestion": "用具体行为替代抽象情绪总结"})

    density = count / total_chars
    if density > 0.015:
        findings.append({"level": "WARN", "message": f"抽象情绪词密度偏高 ({density:.3%})", "suggestion": "减少抽象词，增加动作和物件反应"})
    elif density > 0.008:
        findings.append({"level": "INFO", "message": f"抽象情绪词密度 {density:.3%}", "suggestion": "可适当减少"})

    score = max(0, 100 - count * 12)
    status = "PASS" if score >= 75 else ("WARNING" if score >= 60 else "FAIL")
    return {"guard": "emotion_summary_guard", "status": status, "score": score, "findings": findings, "chapter_no": chapter_no}
