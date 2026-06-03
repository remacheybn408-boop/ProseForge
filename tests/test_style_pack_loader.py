"""test_style_pack_loader.py — Style pack loader tests"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_list_styles():
    from genre.style_loader import list_styles
    styles = list_styles()
    assert "generic" in styles
    assert "webnovel" in styles
    assert "black_humor" in styles
    assert len(styles) >= 8


def test_load_generic():
    from genre.style_loader import load_style_pack
    pack = load_style_pack("generic")
    assert pack["style_id"] == "generic"


def test_load_webnovel():
    from genre.style_loader import load_style_pack
    pack = load_style_pack("webnovel")
    assert pack["style_id"] == "webnovel"


def test_fallback_unknown():
    from genre.style_loader import load_style_pack
    pack = load_style_pack("nonexistent_style")
    assert pack["style_id"] in ("generic", "nonexistent_style")


def test_fallback_none():
    from genre.style_loader import load_style_pack
    pack = load_style_pack(None)
    assert pack["style_id"] == "generic"
