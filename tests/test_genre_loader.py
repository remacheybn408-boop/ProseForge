"""test_genre_loader.py — Genre pack loader tests"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_list_genres():
    from genre.genre_loader import list_genres
    genres = list_genres()
    assert "generic" in genres
    assert "xianxia" in genres
    assert "mystery" in genres
    assert "apocalypse" in genres
    assert len(genres) >= 9


def test_load_generic():
    from genre.genre_loader import load_genre_pack
    pack = load_genre_pack("generic")
    assert pack["genre_id"] == "generic"
    assert "name" in pack
    assert len(pack.get("core_promises", [])) > 0


def test_load_xianxia():
    from genre.genre_loader import load_genre_pack
    pack = load_genre_pack("xianxia")
    assert pack["genre_id"] == "xianxia"
    assert len(pack.get("forbidden_patterns", [])) > 0


def test_load_mystery():
    from genre.genre_loader import load_genre_pack
    pack = load_genre_pack("mystery")
    assert pack["genre_id"] == "mystery"


def test_fallback_unknown():
    from genre.genre_loader import load_genre_pack
    pack = load_genre_pack("nonexistent_genre_xyz")
    assert pack["genre_id"] in ("generic", "nonexistent_genre_xyz")


def test_fallback_none():
    from genre.genre_loader import load_genre_pack
    pack = load_genre_pack(None)
    assert pack["genre_id"] == "generic"
