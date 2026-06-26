from pathlib import Path

from src.guards.human_texture._config import (
    get_genre_presets_path,
    resolve_human_texture_project_root,
)
from src.rag.rag_config import (
    DEFAULT_VECTOR_COLLECTION_NAME,
    DEFAULT_VECTOR_EMBEDDING_MODEL,
    DEFAULT_VECTOR_PERSIST_DIR,
    get_vector_config,
)
from src.rag.vector_retriever import _get_vector_settings


def test_human_texture_config_helpers_resolve_repo_root():
    root = resolve_human_texture_project_root(Path(__file__).resolve())
    expected = root / "configs" / "human_texture" / "genre_presets.yaml"

    assert get_genre_presets_path(Path(__file__).resolve()) == expected
    assert expected.exists()


def test_vector_settings_use_centralized_defaults():
    vector_config = get_vector_config()

    assert vector_config["persist_dir"] == DEFAULT_VECTOR_PERSIST_DIR
    assert vector_config["collection_name"] == DEFAULT_VECTOR_COLLECTION_NAME
    assert vector_config["embedding_model"] == DEFAULT_VECTOR_EMBEDDING_MODEL
    assert _get_vector_settings(None) == (
        DEFAULT_VECTOR_PERSIST_DIR,
        DEFAULT_VECTOR_COLLECTION_NAME,
        DEFAULT_VECTOR_EMBEDDING_MODEL,
    )


def test_vector_settings_respect_overrides():
    assert _get_vector_settings(
        {
            "rag": {
                "vector": {
                    "persist_dir": "tmp/vectors",
                    "collection_name": "custom_chunks",
                    "embedding_model": "custom-model",
                }
            }
        }
    ) == ("tmp/vectors", "custom_chunks", "custom-model")
