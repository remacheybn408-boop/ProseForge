# 8 步流水线参考实现

`chapter_pipeline.py` 设计文档。完整源码见 `scripts/chapter_pipeline.py`。

## 流水线架构

```
main()
  ├── pre  → pre_write_gate()        # 写作前：标题骨架 + 上章brief + 上下文
  └── post → word_count_gate()       # 字数门禁 (<3300 失败)
            → continuity_gate()       # 连续性检查
            → scene_quality_gate()    # 场景质量 (>=4)
            → anti_ai_style_gate()    # 反AI腔 (≤2处轻微)
            → ingest()               # 入库 + brief + run_report
              ├── generate_chapter_brief()   → chapter_briefs/
              └── chapter_run_report.json    → run_reports/
            → stage_review()         # 3章复盘(条件触发)
  volume → volume_post()             # 卷级总结 → volume_reports/

完整调用:
  pre → task_card → write(novel-factory) → post(gates+ingest) → volume_post
```

## Agent 路由闭环 (v0.3.0+)

正文写作必须走 `novel-factory` skill，禁止聊天模式直接生成。详见 `docs/skills/novel_factory_router_SKILL.md`。

每次 ingest 后自动生成 `chapter_run_report.json`：

```json
{
  "mode": "NOVEL_WRITE_MODE",
  "required_skill": "novel-factory",
  "skill_called": true,
  "chapter_no": 1,
  "word_count": 3680,
  "pre_done": true,
  "task_card_done": true,
  "word_count_gate": true,
  "continuity_gate": true,
  "scene_quality_gate": true,
  "anti_ai_style_gate": true,
  "ingest_done": true,
  "next_allowed": true,
  "next_action": "pre_next_chapter"
}
```

自检：

```bash
python scripts/agent_run_guard.py exports/run_reports/chapter_001_run_report.json
# PASS_NOVEL_WRITE_GUARD  或  FAILED_NOVEL_WRITE_GUARD: <原因>
```

guard 不通过 → 章节不得视为完成。

## 字数门禁 (V4)

```python
wc_rules = {"hard_min": 3300, "ideal_min": 3500, "ideal_max": 3900, "normal_max": 4200, "special_max": 5000}

def word_count_gate(content, chapter_no, chapter_type="normal"):
    wc = _count_chinese(content)
    if wc < rules['hard_min']:       return False, wc        # 红灯失败
    if ideal_min <= wc <= ideal_max:  return "ideal", wc     # 最佳
    if hard_min <= wc < ideal_min:    return "pass_but_low", wc  # 偏短
    if ideal_max < wc <= normal_max:  return True, wc        # 正常
    if normal_max < wc <= special_max:                       # 偏长
        return True if climax/final else "oversize", wc
    return "oversize", wc                                    # 超长
```

## 场景质量 (>=4)

```python
def scene_quality_gate(content):
    estimated_scenes = max(scene_markers//2, location_changes, 1)
    passed = estimated_scenes >= 4 and len(issues) < 3
    return passed, issues
```

## 反AI腔

10 项检测（不是A而是B / 那一刻终于明白 / 从未想过 / 他意识到 / 这意味着 / 像一座雕像 / 沉默了几秒 / 救赎 / 硬科普 / 论文式），≤2 处轻微通过。

## 输出文件

| 阶段 | 输出 | 位置 |
|------|------|------|
| pre | context_pack.txt | exports/ |
| pre | pipeline_state.json | exports/pipeline_state/ |
| post | chapter_brief.json | exports/chapter_briefs/ |
| post | chapter_run_report.json | exports/run_reports/ |
| volume | volume_report.json | exports/volume_reports/ |

## 调用示例

```bash
# 配置驱动调用
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel
python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel
python scripts/chapter_pipeline.py volume --config config.json --novel-slug demo_novel --volume-no 1

# 自检
python scripts/agent_run_guard.py exports/run_reports/chapter_001_run_report.json
```
