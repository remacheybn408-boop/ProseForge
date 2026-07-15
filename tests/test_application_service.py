from src.application.pipeline_service import PipelineService, PreChapterRequest


def test_pipeline_service_routes_pre_through_pipeline_context(tmp_path, monkeypatch):
    captured = {}

    def fake_pre(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "chapter_no": kwargs["chapter_no"]}

    import src.pipeline.pre as pre_module
    monkeypatch.setattr(pre_module, "run_pre", fake_pre)

    result = PipelineService().pre(
        PreChapterRequest(
            project_root=tmp_path,
            novel_slug="novel_a",
            novel_title="Novel A",
            chapter_no=3,
        )
    )

    assert result["chapter_no"] == 3
    assert captured["context"].novel_slug == "novel_a"
    assert captured["context"].project_root == tmp_path
