"""test_punctuation_guard.py — 标点节奏门禁测试"""

from src.guards.punctuation_guard import run_punctuation_check


def _make_dash_text(n):
    """生成含 n 组 '——' 的文本"""
    lines = []
    for i in range(n):
        lines.append(f"这是第{i+1}组破折号——用来测试的——内容。")
    return "\n".join(lines)


def _make_drag_dialogue():
    return "许铁牛说，掉——水——里——了。你让开。"


class TestPunctuationCounting:
    def test_count_dashes_normal(self):
        text = _make_dash_text(5)
        result = run_punctuation_check(text)
        s = result["status"]
        assert result["stats"]["dash_pairs"] >= 5, f"expected >=5, got {result['stats']['dash_pairs']}"

    def test_count_single_dash(self):
        text = "他看了一眼——然后走了。单独一个破折号——没有成对。"
        result = run_punctuation_check(text)
        # Guard counts total dashes (including ——), single — is near-zero after removing ——
        assert result["stats"]["total_dashes"] >= 3

    def test_count_ellipsis(self):
        text = "他想了想……然后说……算了。还有一个..."
        result = run_punctuation_check(text)
        assert result["stats"]["ellipsis_count"] >= 3

    def test_count_exclamation(self):
        text = "站住！不许动！！快跑！！！"
        result = run_punctuation_check(text)
        assert result["stats"]["exclamation_count"] >= 3


class TestDashThresholds:
    def test_dash_warning_threshold(self):
        text = _make_dash_text(11)
        result = run_punctuation_check(text)
        s = result["status"]
        assert s in ("WARNING", "FAIL"), f"11 dashes should trigger WARN, got {s}"

    def test_dash_fail_threshold(self):
        text = _make_dash_text(16)
        result = run_punctuation_check(text)
        assert result["status"] == "FAIL", f"16 dashes should FAIL, got {result['status']}"


class TestMultiDashInParagraph:
    def test_same_paragraph_multi_dash(self):
        # Need >100 chars for density check + multiple dashes in one paragraph
        text = "一段里出现了破折号，这是第一个。然后又有了第二个——这样就是两个了。接着第三个——看，三个了。第四个也来了——四个！第五个——五个。这句话本身很长，用来凑够一百个字符以上的文本长度，确保门禁的密度检查不会被短文本豁免规则跳过。加上这些字应该够了。"
        result = run_punctuation_check(text)
        findings = result.get("findings", [])
        assert any("段落" in f.get("type", "") or "破折号密度" in f.get("type", "") for f in findings), f"expected dash finding, got {[f['type'] for f in findings]}"

    def test_dialogue_drag_dash(self):
        text = _make_drag_dialogue()
        result = run_punctuation_check(text)
        assert result["status"] != "FAIL", f"drag dialogue should not FAIL, got {result['status']}"
        # Verify drag dashes detected via classification
        assert result["stats"]["dash_classification"]["对话拖音/喜剧型"]


class TestEdgeCases:
    def test_empty_text(self):
        result = run_punctuation_check("")
        assert result["status"] == "PASS", f"empty should PASS, got {result['status']}"

    def test_normal_text_pass(self):
        text = "林观澜走到井边，打了一桶水。水面在桶里晃了几下，慢慢平静下来。他盯着水面看了一会儿。"
        result = run_punctuation_check(text)
        assert result["status"] == "PASS", f"normal text should PASS, got {result['status']}"
