# 8 步流水线参考实现

本章节是 `chapter_pipeline.py` 的设计文档，完整源码见 `scripts/chapter_pipeline.py`。

## 流水线架构

```
main()
  ├── pre  → pre_write_gate()       # 写作前：加载上下文
  └── post → word_count_gate()      # 字数门禁
            → continuity_gate()      # 连续性检查
            → scene_quality_gate()   # 场景质量
            → anti_ai_style_gate()   # 反AI腔
            → ingest()              # 入库
            → stage_review()        # 3章复盘(条件触发)
```

## 字数门禁实现

```python
WORD_RULES = {
    "normal":  {"target": 3700, "min": 3300, "max": 4200, "fail": 3000},
    "climax":  {"target": 4500, "min": 4200, "max": 5000, "fail": 3000},
    "final":   {"target": 5000, "min": 4500, "max": 6000, "fail": 3000},
    "short":   {"target": 3200, "min": 3000, "max": 3300, "fail": 2800},
}

def word_count_gate(content, chapter_no, chapter_type="normal"):
    rules = WORD_RULES.get(chapter_type, WORD_RULES["normal"])
    wc = _count_chinese(content)
    
    if rules['min'] <= wc <= rules['max']:
        return True, wc                        # 正常通过
    elif rules['fail'] <= wc < rules['min']:
        if vcount >= 3:
            return "patch_suspect", wc         # 疑似凑数
        return "yellow", wc                    # 黄灯
    else:
        return False, wc                       # 红灯失败
```

## 场景质量检测

```python
def scene_quality_gate(content):
    # 检测场景标记（时间词+地点词）
    scene_markers = re.findall(r'(第.*天|早上|傍晚|...|站在|蹲在)', content)
    location_changes = len(set(re.findall(r'(杂役院|劈柴场|矿洞|...)', content)))
    estimated_scenes = max(len(scene_markers)//2, location_changes, 1)
    
    # 检查水症
    issues = []
    if summary_lines > 5: issues.append("总结腔过多")
    if dialogue_lines < 3: issues.append("对话过少")
    if action_verbs < 15: issues.append("动作描写过少")
    
    return estimated_scenes >= 3 and len(issues) < 3, issues
```

## 反AI腔检测

```python
def anti_ai_style_gate(content):
    checks = {
        "不是A而是B": re.findall(r'不是.{2,10}而是', content),
        "那一刻终于明白": re.findall(r'那一刻.{0,5}终于明白', content),
        "从未想过": re.findall(r'从未想过|从未见过|从未感受过', content),
        "他意识到": re.findall(r'他意识到|他明白', content),
        "这意味着": re.findall(r'这意味着|这说明|这代表', content),
        "沉默了几秒": re.findall(r'沉默了几秒|沉默了.{1,4}秒', content),
        "救赎": re.findall(r'救赎|他就是她的|她就是他的', content),
        "硬科普": re.findall(r'公式|定律|方程|定理|热力学|量子力学|相对论', content),
        "论文式": re.findall(r'通过.{5,20}实现了|基于.{5,20}进行了|本质上是|事实上', content),
    }
    total = sum(len(v) for v in checks.values())
    return total <= 2, [...]  # ≤2处轻微通过，>2处不通过
```

## Pipeline State 文件锁

```python
# pre 完成后保存状态
state = {
    "chapter_no": chapter_no,
    "pre_done": True,
    "previous_tail_loaded": True,
    "allowed_to_write": True,
    "timestamp": now()
}
state_path.write_text(json.dumps(state, ...))

# post 前验证
if not state_path.exists() or not state.get("allowed_to_write"):
    sys.exit(1)  # 禁止 post
```

## 版本管理

```python
# ingest 时自动保存版本
vno = cur.execute("SELECT COALESCE(MAX(version_no),0) FROM chapter_versions WHERE ...").fetchone()[0] + 1
cur.execute("INSERT INTO chapter_versions(...version_no, version_status, content, word_count...) VALUES(..., 'draft', ...)")
```

## 调用示例

```bash
# 普通章节
python chapter_pipeline.py pre 4 --type normal
python chapter_pipeline.py post 4 --type normal

# 高潮章节
python chapter_pipeline.py pre 10 --type climax
python chapter_pipeline.py post 10 --type climax

# 3章复盘
python chapter_pipeline.py review 6
```
