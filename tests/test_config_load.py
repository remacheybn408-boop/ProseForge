"""test_config_load.py — 配置加载测试

v0.8.3 (M11): NamedTemporaryFile(delete=False) → tmp_path / "config.json"。
"""
import json
from pathlib import Path

from src.pipeline._base import load_config
from src.utils.config_utils import normalize_config


class TestConfigLoad:
    def test_default_config(self):
        """No config file -> defaults — verify structure, not values (env-dependent)"""
        cfg = load_config("/nonexistent/path.json")
        assert isinstance(cfg["db_path"], str) and len(cfg["db_path"]) > 0
        assert isinstance(cfg["word_count"], dict)
        assert isinstance(cfg["word_count"]["normal"], dict)
        assert isinstance(cfg["word_count"]["normal"]["min"], int)
        assert isinstance(cfg["scene_quality"], dict)
        assert isinstance(cfg["scene_quality"]["min_effective_scenes"], int)

    def test_load_config_file(self, tmp_path):
        """Custom config overrides defaults"""
        custom = {
            "db_path": "/custom/path.db",
            "word_count": {"normal": {"min": 1900, "best_min": 1900, "best_max": 2800, "max": 3300}},
        }
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps(custom), encoding="utf-8")

        cfg = load_config(str(cfg_path))
        assert cfg["db_path"] == "/custom/path.db"
        assert cfg["word_count"]["normal"]["min"] == 1900

    def test_gates_word_count_no_longer_overrides_word_count(self):
        """Legacy gates.word_count must not override the canonical top-level word_count."""
        cfg = normalize_config({
            "gates": {
                "word_count": {
                    "min_normal_chapter": 9999,
                    "target_normal_chapter": 9999,
                    "target_long_chapter": 9999,
                }
            },
            "word_count": {
                "normal": {"min": 1300, "best_min": 1900, "best_max": 2800, "max": 3300}
            },
            "allow_short_chapter": True,
        })
        assert cfg["word_count"]["normal"]["min"] == 1300
        assert cfg["word_count"]["normal"]["best_min"] == 1900
        assert cfg["word_count"]["normal"]["max"] == 3300
        assert cfg["allow_short_chapter"] is True

    def test_example_config_uses_canonical_word_count_only(self):
        """config.example.json should expose only the canonical word_count shape."""
        cfg_path = Path(__file__).resolve().parents[1] / "config.example.json"
        payload = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert "word_count" not in payload.get("gates", {})
        assert isinstance(payload.get("word_count"), dict)
        assert payload["allow_short_chapter"] is True
