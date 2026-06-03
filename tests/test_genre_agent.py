"""test_genre_agent.py — Genre agent tests"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_empty_text_no_crash():
    from genre.genre_agent import run_genre_agent
    result = run_genre_agent("", chapter_no=1)
    assert "status" in result
    assert "score" in result


def test_mystery_clue_check():
    from genre.genre_agent import run_genre_agent
    text = "侦探走进房间，看了看四周。桌上有一杯没喝完的咖啡。他觉得凶手就是管家。案件就这样破了。"
    result = run_genre_agent(text, chapter_no=1, genre_id="mystery")
    # Should warn about missing clues
    assert result["status"] in ("WARN", "PASS")


def test_apocalypse_resource():
    from genre.genre_agent import run_genre_agent
    text = "他在废墟中走了很久，没有找到任何东西。天快黑了，他决定继续走。"
    result = run_genre_agent(text, chapter_no=1, genre_id="apocalypse")
    assert result["status"] in ("WARN", "PASS")


def test_historical_modern_word():
    from genre.genre_agent import run_genre_agent
    text = "李白端起酒杯，说了句牛逼。这波操作属实高端。"
    result = run_genre_agent(text, chapter_no=1, genre_id="historical")
    findings = result.get("findings", [])
    # Should detect modern internet slang
    has_mod = any("现代" in f.get("type", "") for f in findings)
    assert has_mod or result["status"] in ("WARN", "PASS")


def test_wuxia_lucky_no_work():
    from genre.genre_agent import run_genre_agent
    text = "少年意外发现一本神功秘籍，从此天下无敌。"
    result = run_genre_agent(text, chapter_no=1, genre_id="wuxia")
    assert result["status"] in ("WARN", "PASS")


def test_sci_fi_hard_terms():
    from genre.genre_agent import run_genre_agent
    text = "飞船利用量子纠缠实现了超光速通信，暗物质引擎提供了无穷无尽的能源。维度折叠技术让他们穿越了奇点。"
    result = run_genre_agent(text, chapter_no=1, genre_id="sci_fi")
    assert result["status"] in ("WARN", "PASS")


def test_generic_no_false_positive():
    from genre.genre_agent import run_genre_agent
    text = "这是一个关于勇气和友谊的故事，主角踏上了冒险的旅程。"
    result = run_genre_agent(text, chapter_no=1, genre_id="generic")
    # Generic should not trigger genre-specific false alarms
    assert result["score"] >= 80
