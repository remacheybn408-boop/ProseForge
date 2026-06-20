"""rhythm_guard.py — 节奏过稳检测 v0.6.6"""
import re, statistics

def run_rhythm_check(content: str, chapter_no: int = 0) -> dict:
    sentences = [s.strip() for s in re.split(r'[。！？\n]+', content) if len(s.strip()) > 3]
    paragraphs = [p.strip() for p in content.split('\n') if len(p.strip()) > 10]
    findings = []
    score = 100

    if not sentences:
        return {"guard": "rhythm_guard", "status": "PASS", "score": 100, "findings": []}

    # 句长统计
    lengths = [len(s) for s in sentences]
    avg = statistics.mean(lengths)
    std = statistics.stdev(lengths) if len(lengths) > 1 else 0
    short_ratio = sum(1 for l in lengths if l <= 8) / len(lengths)
    long_ratio = sum(1 for l in lengths if l >= 40) / len(lengths)

    if std < 6:
        findings.append({"level": "WARN", "message": f"句长标准差偏低 ({std:.1f})，句子长度过于均匀", "suggestion": "加入一些短句或长句打破节奏"})
        score -= 15
    if short_ratio < 0.05:
        findings.append({"level": "WARN", "message": f"超短句比例过低 ({short_ratio:.1%})，缺少急促停顿", "suggestion": "在关键情绪处加入短句/单字句"})
        score -= 10
    if long_ratio < 0.03:
        findings.append({"level": "INFO", "message": f"超长句比例偏低 ({long_ratio:.1%})", "suggestion": "可适当加入带插入语的长句丰富节奏"})
        score -= 5

    # 段落长度统计
    para_lens = [len(p) for p in paragraphs]
    if len(para_lens) > 3:
        p_std = statistics.stdev(para_lens) if len(para_lens) > 1 else 0
        if p_std < 20:
            findings.append({"level": "WARN", "message": "段落长度过于平均", "suggestion": "让段落长短错落"})
            score -= 10

    status = "PASS" if score >= 70 else ("WARNING" if score >= 55 else "FAIL")
    return {"guard": "rhythm_guard", "status": status, "score": max(0, score), "findings": findings, "chapter_no": chapter_no}
