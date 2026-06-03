"""cliche_sentence_guard.py — 套路句式检测 v0.6.6"""
import re

CLICHE_PATTERNS = [
    (r"不是.{2,10}而是", "不是A而是B"),
    (r"他没有回答[，,。].*只是", "他没有回答，只是…"),
    (r"她不知道的是", "她不知道的是…"),
    (r"空气安静[下来了下]", "空气安静下来"),
    (r"时间仿佛[停住凝固]", "时间仿佛停住了"),
    (r"心里有什么[东西事].*[动了一下一暖一沉]", "心里有什么东西动了一下"),
    (r"说不上来那是什么[感觉滋味]", "说不上来那是什么感觉"),
    (r"眼神复杂", "眼神复杂"),
    (r"那一刻[，,].*终于[明白意识到]", "那一刻终于明白"),
    (r"仿佛有什么[东西事]在", "仿佛有什么在改变"),
    (r"她没有再说话", "她没有再说话"),
    (r"他只是笑了笑", "他只是笑了笑"),
    (r"像[一].*[落进掉入]心里", "像…落进心里"),
    (r"一切都回不去了", "一切都回不去了"),
    (r"命运的齿轮", "命运的齿轮"),
    (r"心里一紧|心里一沉|心里一酸", "心里一紧/沉/酸"),
]

def run_cliche_check(content: str, chapter_no: int = 0) -> dict:
    findings = []
    count = 0

    for pattern, name in CLICHE_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            count += len(matches)
            findings.append({"level": "WARN", "message": f"套路句式「{name}」出现 {len(matches)} 次", "suggestion": "替换为更具体的动作或物件反应"})

    score = max(0, 100 - count * 10)
    status = "PASS" if count <= 3 else ("WARNING" if count <= 6 else "FAIL")
    return {"guard": "cliche_sentence_guard", "status": status, "score": score, "findings": findings, "chapter_no": chapter_no}
