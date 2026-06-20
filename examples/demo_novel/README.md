# Demo Novel

这是 `novel-pipeline-write-engine` 的最小可运行示例。

## 包含

- `outline_skeleton.json` — 一卷 25 章完整标题骨架
- 每章包含：planned_title / chapter_goal / conflict_point / ending_hook_direction

## 使用方式

```bash
# 1. 初始化数据库
python scripts/init_db.py --config config.json

# 2. 导入标题骨架
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json

# 3. 写第 1 章
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel
# ... 撰写 TXT ...
python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel

# 4. 继续下一章
python scripts/chapter_pipeline.py pre 2 --config config.json --novel-slug demo_novel

# 5. 卷级总结
python scripts/chapter_pipeline.py volume --config config.json --novel-slug demo_novel --volume-no 1

# 测试
pytest tests/ -v
```
