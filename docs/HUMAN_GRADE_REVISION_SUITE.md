# Human-Grade Revision Suite (v0.4.0)

> 拟人审稿质量套件 — 不是 AI 检测器，是质量提升工具链。

v0.4.0 Human-Grade Revision Suite 是一套拟人审稿质量门禁，旨在提升小说稿件的自然度、原创感、连续性和投稿前可检查性。它不是 AI 率检测器，不输出任何"人类率"或"平台过检率"。所有门禁（除合规自查外）均为 WARNING 级别，不阻断入库流程。

---

## 核心原则

> 稿件不是"通过 AI 检测"，而是"读起来像人写的"。

本套件不对内容做真假标签判断，而是从七个维度检查稿件是否具备人类写作的特征：

1. **审稿痕迹** — 初稿常有过度解释、冗余修饰和"写给你看"的痕迹
2. **具体锚点** — 人类写作天然绑定具体物件、身体动作和场景细节
3. **场景因果** — 故事推进需要原因→行动→阻力→代价→结果
4. **对白自然度** — 真实对话有打断、未完成句子和动作节拍
5. **句式变化** — 避免段落开头单一、抽象词堆砌、句长过平
6. **投稿合规** — 自查内容是否触碰投稿平台红线（暴力/色情/敏感）
7. **最终投稿报告** — 汇总所有门禁结果，给出投稿建议和待修改项

---

## 7 个模块详解

### 1. Editor Revision Guard (审稿痕迹检查)

**原理**: 初稿常有"过度解释综合征" — 作者/模型担心读者不懂，反复解释同一件事。

**检测项**:
- 过度解释比例 (over-explained ratio): 检测 "也就是说"、"换句话说"、"这意味着" 等复述句式
- 审稿纹理感 (revision texture): 成熟稿件通常有适当的省略、读者自行补全的空间。过于完整的解释链往往暴露初稿痕迹

**报告**: `editor_revision_report.json` — 输出过度解释比例和纹理评分

**级别**: WARNING only, 不阻断

---

### 2. Concrete Anchor Guard (具体锚点守卫)

**原理**: 人类写作天然绑定具体物件和身体动作。抽象心理描写如果没有具体锚点（物件/动作/场景）锚定，会显得飘忽、失去真实感。

**检测项** (500字窗口):
- 物件锚点 (object anchor): 是否有具体可触知的物品
- 身体动作锚点 (body action anchor): 是否有身体层面的具体动作
- 场景锚点 (scene anchor): 是否有场景层面的具体描述
- 锚点密度 (min_anchor_density >= 0.22): 每500字中锚点出现的比例

**报告**: `concrete_anchor_report.json`

**级别**: WARNING only, 不阻断

---

### 3. Scene Causality Guard (场景因果链)

**原理**: 有效叙事需要因果链驱动，而非事件堆砌。每个重要场景应该具备 CARCRH 要素。

**检测项** (CARCRH 模型):
- **C**ause (原因): 为什么发生这件事
- **A**ction (行动): 角色做了什么具体行动
- **R**esistance (阻力): 行动遇到什么阻力
- **C**ost (代价): 行动付出了什么代价
- **R**esult (结果): 事件导致了什么新状态
- **H**ook (钩子, 可选): 是否留下悬念钩子

**报告**: `scene_causality_report.json` — 输出每场景的 CARCRH 完整度

**级别**: WARNING only, 不阻断

---

### 4. Dialogue Naturalness Guard (对白自然度)

**原理**: 真实对话有打断、未完成句子、称呼变化和伴随动作。书面化的完整句子轮替是 AI 腔的典型特征。

**检测项**:
- 对白变化度 (min_dialogue_variation_score >= 0.18): 对话是否单一模式
- 打断偏好 (prefer_interruption): 检查是否有打断句式
- 未完成句 (prefer_unfinished_sentence): 检查是否有话说一半的句子
- 动作节拍 (prefer_action_beats): 对话是否有伴随的动作描写

**报告**: `dialogue_naturalness_report.json`

**级别**: WARNING only, 不阻断

---

### 5. Style Variation Guard (句式变化守卫)

**原理**: 模板化写作常见特征：段落开头单一、抽象词过度使用、句长缺乏变化。

**检测项**:
- 段落开头重复率 (max_repeated_opening_ratio <= 0.25): 检测 "她...她...她..." 或 "于是...于是...于是..." 等重复开头
- 抽象词过度使用 (max_overused_abstract_words <= 12): 检测 "命运"、"人生"、"岁月" 等空泛词的密度
- 句长变化度 (min_sentence_length_variance >= 0.35): 短句和长句是否交替出现

**报告**: `style_variation_report.json`

**级别**: WARNING only, 不阻断

---

### 6. Compliance Selfcheck Guard (投稿合规自查)

**原理**: 在提交前对稿件做合规风险自查，避免因内容违规被平台拒绝。

**检测项**:
- 高风险内容 (block_high_risk): 明显的暴力/色情/敏感内容 — **可 BLOCK 阻断入库**
- 中风险内容 (warn_medium_risk): 边界模糊的内容 — WARNING 提示

**注意**: 这是唯一可以阻断入库的门禁。当合规自查返回 BLOCK 状态时，流水线将停止并提示修改。

**报告**: `compliance_selfcheck_report.json`

**级别**: 可 BLOCK (唯一可阻断的门禁)

---

### 7. Final Submission Report (最终投稿报告)

**原理**: 汇总前 6 个门禁的检查结果，给出一份投稿建议报告。

**输出**:
- 所有门禁的通过/警告/阻止状态
- Top N 项建议修改的优先级列表 (top_revision_tasks)
- 总体投稿建议: 建议提交 / 建议修改后提交 / 不建议提交

**报告**: `final_submission_report.json`

**级别**: 纯报告，不执行任何阻断

---

## 与现有流水线的集成

```
现有流水线 (V4.1):  pre → task_card → write → word_count → continuity →
                     scene → anti_ai → padding → voice_guards → qgp → ingest

v0.4.0 新增步骤 (V4.2):  ... → qgp →
                     editor_revision → concrete_anchor → scene_causality →
                     dialogue_naturalness → style_variation →
                     compliance_selfcheck → final_submission_report → ingest
```

所有新门禁均为 try/except 包裹，导入失败或执行异常时打印 `[WARN] skipped` 继续执行，不阻塞流水线。

唯一例外: `compliance_selfcheck` 返回 BLOCK 状态时，打印 `[BLOCK]` 并 `sys.exit(1)` 停止入库。

---

## 配置

在 `config.json` 中新增 `human_grade_revision` 段：

```json
{
  "human_grade_revision": {
    "enabled": true,
    "version": "v0.4.0",
    "mode": "warning_first",
    "quality_guards_warning_only": true,
    "compliance_guard_can_block": true,
    ...
  }
}
```

详见 `config.example.json`。

---

## 重要声明

- 本项目不提供 AI 率、人类率或平台过检率
- 所有门禁基于启发式规则，不依赖外部 API
- 门禁结果仅作写作质量参考，不能替代人工审稿
- 合规自查基于关键词匹配，可能有误报，请结合实际情况判断

---

详见: [v0.4.0 Release Notes](V0.4.0_RELEASE_NOTES.md) | [Pipeline 文档](pipeline.md)
