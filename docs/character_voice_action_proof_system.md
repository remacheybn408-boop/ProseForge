# 角色口吻与动作证据系统 (Character Voice & Action Proof System)

版本: v0.3.1 Quality Guard Patch

## 概述

本系统在 v0.3.1 证据门禁基础上，为长篇小说写作流水线增加两类能力：

1. **角色口吻系统**：确保每个角色说话不一样，有独特的声音、方言浓度、文言浓度、口头禅和情感表达方式。
2. **动作化叙事系统**：禁止 AI 总结腔，要求用具体动作、停顿、误会、代价来推进叙事。

## 核心原则

> 门禁不能只硬，还要准。角色不能同声，结尾不能空喊，情绪不能只靠总结。

## 系统组成

### 1. 角色口吻卡 (Character Voice Profile)

每个主要角色定义 14 项声音属性：

| 属性 | 说明 | 示例 |
|------|------|------|
| identity | 角色身份 | "灵矿底层老人" |
| voice_type | 声音类型 | "市井经验派" |
| region_flavor | 地域味道 | "轻北方口语" |
| dialect_level | 方言浓度 (0-5) | 2 |
| wenyan_level | 文言浓度 (0-5) | 0 |
| sentence_length | 句长偏好 | "短句为主" |
| speech_rhythm | 说话节奏 | "慢，有停顿" |
| favorite_words | 惯用词 | ["甭", "娃子", "听风"] |
| forbidden_words | 禁用词 | ["因此", "命运"] |
| emotion_style | 情感表达方式 | "嘴硬心软" |
| action_habits | 动作习惯 | ["磕烟袋", "摸矿壁"] |
| misunderstanding_triggers | 误会触发器 | ["看见宗门标记..."] |
| cost_pattern | 代价模式 | "愿意替年轻人挡祸" |
| sample_lines | 示例对白 | ["娃子，甭往前凑。"] |

### 2. 场景动作卡 (Scene Action Card)

每章重要场景必须包含至少 2 项：

1. **具体动作 (action_beat)**: 人物在做什么具体的物理动作。
2. **停顿或沉默 (pause_beat)**: 对白之间有停顿、沉默、犹豫。
3. **误会或错误判断 (misunderstanding_beat)**: 至少一个人物做了一次错误判断。
4. **代价或损失 (cost_beat)**: 场景结尾有人物付出了真实代价。

### 3. 方言系统

| 角色类型 | 推荐方言浓度 |
|----------|------------|
| 主角 | 0% — 5% |
| 女主/重要角色 | 0% — 10% |
| 普通配角 | 5% — 15% |
| 市井人物/矿工/老人 | 10% — 25% |
| 旁白 | 0% |

规则：
- 方言只用于对白，旁白保持清晰。
- 不同角色方言浓度不同，不能所有底层角色说同一种方言。
- 关键剧情句必须让普通读者看懂。

### 4. 文言/古雅语体系统

| 角色类型 | 推荐文言浓度 |
|----------|------------|
| 主角 | 0% — 5% |
| 师尊/长老 | 10% — 25% |
| 宗门律令 | 30% — 60% |
| 古籍/碑文/阵法口诀 | 50% — 80% |
| 反派高位修士 | 10% — 30% |
| 旁白 | 5% — 15% |

规则：
- 禁止整段全古文、大量生僻字。
- 禁止用文言掩盖剧情空洞。
- 关键剧情不能藏在难懂的文言里。
- 一句古雅语后面最好有动作或结果承接。

### 5. Show, Don't Tell 禁止模式

以下句式在旁白中触发 WARNING：

- "他终于明白..."
- "真正的危机才刚刚开始"
- "命运的齿轮开始转动"
- "关系发生了微妙的变化"
- "前所未有的恐惧"
- "多年以后回想起..."
- "要知道...从来都不是..."

详见 `docs/voice/show_dont_tell_forbidden_patterns.json`。

### 6. 具体钩子系统

每章结尾必须绑定以下 5 种 anchor 之一：

| 类型 | 说明 | 示例 |
|------|------|------|
| object | 物件异常 | "碎铜钱里露出一根黑色细线" |
| person | 人物出现/消失/反转 | "门外站着三天前下葬的老矿头" |
| location | 地点变化 | "三号支洞的入口不见了" |
| relationship | 关系突变 | "师姐把剑横在他喉前" |
| cost | 代价显现 | "他发现自己记不起母亲的名字了" |

禁止的空泛钩子：
- "真正的危机才刚刚开始"
- "风暴即将来临"
- "没人知道等待他们的是什么"
- "命运的齿轮开始转动"

## 门禁流程

```
pre
→ task_card
→ character_voice_load          (新: 加载角色口吻卡)
→ scene_action_card             (新: 加载场景动作卡)
→ scene_or_beat_plan            (Phase 1: 节拍规划)
→ write_chunks
→ assemble_chapter
→ word_count
→ continuity_evidence_guard     (Phase 1: 硬/软状态分层)
→ canon_evidence_guard
→ scene_delta_guard             (Phase 1: narrative beats)
→ anti_ai
→ padding_guard
→ character_voice_guard         (新: Phase 3, 先 WARNING)
→ classical_register_guard      (新: Phase 3, 先 WARNING)
→ show_dont_tell_guard          (新: Phase 3, 先 WARNING)
→ concrete_hook_guard           (新: Phase 3)
→ dialogue_beat_guard           (新: Phase 3)
→ human_revision_report         (新: 汇总所有新门禁结果)
→ ingest
```

## 升级策略

- **Phase 2 (当前)**: 角色口吻与动作门禁以 WARNING 为主，不 FAIL。
- **Phase 3 (稳定后)**: 关键门禁（concrete_hook、dialogue_beat）升级为 FAIL。
- **硬门禁不变**: continuity_evidence 和 canon_evidence 的 hard_state / hard_hook 仍然 FAIL。

## 相关文件

- `docs/voice/character_voice_profiles.example.json` — 角色口吻卡模板
- `docs/voice/scene_action_card.example.json` — 场景动作卡模板
- `docs/voice/show_dont_tell_forbidden_patterns.json` — AI 腔禁用模式
- `scripts/character_voice_guard.py` — 角色口吻门禁
- `scripts/classical_register_guard.py` — 文言/古雅语体门禁
- `scripts/show_dont_tell_guard.py` — 总结句检测门禁
- `scripts/concrete_hook_guard.py` — 具体钩子门禁
- `scripts/dialogue_beat_guard.py` — 对白节拍门禁
