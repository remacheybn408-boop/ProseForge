import sqlite3

import pytest

pytest.importorskip("chromadb")
pytest.importorskip("sentence_transformers")

from src.rag import index_worldbuilding, search_worldbuilding


@pytest.fixture
def worldbuilding_env(tmp_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO novels(slug, title, status) VALUES(?, ?, ?)",
        ("rag-worldbuilding", "RAG Worldbuilding Test", "planning"),
    )
    novel_id = cur.lastrowid

    rows = [
        (
            novel_id,
            "法器",
            "雷劫器",
            "修炼者突破大境界时会引来雷劫。雷劫器是专门承接天雷、导引雷电淬体的法器，"
            "常在突破仪式中布置在阵眼中央。",
            5,
        ),
        (
            novel_id,
            "交通",
            "寒魄舟",
            "寒魄舟依靠冰脉灵晶航行，适合穿越极寒海域，与雷电和突破仪式无关。",
            3,
        ),
        (
            novel_id,
            "地理",
            "星纹药田",
            "星纹药田只能在月光最强的梯田里培育灵草，重点是土壤和潮汐节律。",
            4,
        ),
        (
            novel_id,
            "阵法",
            "护城灯阵",
            "护城灯阵用于夜间巡防和城门示警，依赖火种共鸣，不承担天雷。",
            2,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO worldbuilding(novel_id, category, title, content, importance)
        VALUES(?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    cfg = {
        "db_path": str(tmp_db),
        "rag": {
            "vector": {
                "persist_dir": str(tmp_path / "rag_store"),
                "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
            }
        },
    }
    return novel_id, cfg


def test_index_worldbuilding_and_search(worldbuilding_env):
    novel_id, cfg = worldbuilding_env

    first = index_worldbuilding(cfg)
    assert first["status"] == "ok"
    assert first["total"] == 4
    assert first["indexed"] == 4
    assert first["skipped"] == 0

    second = index_worldbuilding(cfg)
    assert second["status"] == "ok"
    assert second["total"] == 4
    assert second["indexed"] == 0
    assert second["skipped"] == 4

    result = search_worldbuilding(
        "修炼者突破时遭遇的雷电法器",
        novel_id=novel_id,
        top_k=3,
        config=cfg,
    )
    assert result["status"] == "ok"
    assert result["results"]
    assert result["results"][0]["title"] == "雷劫器"

    empty = search_worldbuilding(
        "无关查询：今天天气真好",
        novel_id=999,
        top_k=2,
        config=cfg,
    )
    assert empty["status"] == "ok"
    assert empty["results"] == []
