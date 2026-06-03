# QGP 困惑度质量门禁 (Quality Guard Perplexity)

版本: v0.3.1-qgp

## 1. QGP 是什么

QGP（Quality Guard Perplexity）是一个统计观察层门禁。它通过分析章节文本的 ngram 惊讶度、句长节奏、重复短语、抽象总结密度、具体锚点密度、对白变化度等指标，辅助发现：

1. **过度模板化**：文字太顺、太平均，段落和句长缺乏变化。
2. **节奏过平**：句式太稳定，缺少长短句交替。
3. **重复套话**：常见短语反复出现。
4. **抽象总结过多**：用 AI 总结腔代替具体动作和物件。
5. **对白缺乏辨识度**：所有角色说话方式雷同。
6. **异常混乱**：方言/文言/错字导致文本断裂。

## 2. QGP 不是 AI 检测器

**QGP 不判断文本是否是 AI 写的，不输出 AI 率，不承诺平台检测结果。**

- 传统 AI 检测器依赖大语言模型的困惑度（PPL）来猜测文本来源。
- QGP 使用纯统计 ngram 方法，计算的是"文本风格是否过度平滑/模板化"。
- 一个人类作者写的高度模板化文本，QGP 同样会标 WARNING。
- 一个使用大量方言、文言、口癖的 AI 生成文本，QGP 可能标为"异常混乱"。

QGP 只回答一个问题：**这章是不是太平均 / 太顺 / 太乱？**

## 3. 为什么只做 WARNING

- QGP 是统计观察，不是事实判断。
- 低惊讶度不一定坏（平淡过渡段可能需要），高惊讶度不一定好（可能只是错字多）。
- 方言、文言、角色口癖等高"惊讶"元素是小说的合法艺术手段。
- QGP 永远不阻断章节入库（`hard_fail = false`）。
- `status` 字段只能是 `PASS` 或 `WARNING`，绝不会输出 `FAIL`。

## 4. 如何建立基线

```bash
# 放入 3-5 章作者满意的样本到目录
mkdir -p examples/demo_novel/baseline_chapters
cp 第1章.txt 第2章.txt 第3章.txt examples/demo_novel/baseline_chapters/

# 构建基线
python scripts/qgp_baseline.py build \
  --input-dir examples/demo_novel/baseline_chapters \
  --novel-slug demo_novel \
  --out data/qgp_baselines/demo_novel.qgp_baseline.json
```

建立基线后，QGP 会将新章与自己的风格基线对比，而不是与通用语料对比。

如果没有基线：QGP 仍可运行，但报告中 `baseline_status = "missing"`，建议里会提醒用户先放入样本。

## 5. 如何看报告

```bash
python scripts/perplexity_quality_guard.py \
  --input chapter_001.txt \
  --chapter-no 1 \
  --novel-slug demo_novel \
  --config config.json \
  --out reports/perplexity_quality_report.json
```

报告关键字段：

| 字段 | 说明 |
|------|------|
| `summary.avg_qgp_score` | 平均 ngram 惊讶度 (0-100)，越低越模板化 |
| `summary.template_risk_ratio` | 重复短语比例 |
| `summary.rhythm_flatness` | 节奏平坦度 (0-1)，越高越平 |
| `summary.dialogue_variation_score` | 对白变化度 (0-1)，越高越好 |
| `summary.concrete_anchor_ratio` | 具体物件锚点密度 |
| `summary.abstract_summary_ratio` | 抽象总结词密度 |
| `flags` | 触发的 WARNING 列表 |
| `suggestions` | 可执行的改进建议 |

## 6. 方言 / 文言 / 口癖为什么会让分数波动

- **方言词**（如"甭""俺们""咋了"）在 ngram 中属于罕见组合，会推高惊讶度。
- **文言词**（如"然则""盖""矣"）同样罕见，会拉高惊讶度。
- **角色口癖**（如反复使用某个特殊词）可能被标记为"重复短语"。

这些都是**正常波动**，不是质量问题。QGP 只报告，不硬拦。

如果 `character_voice_guard` 通过了角色口吻检查，QGP 的 WARNING 应该被视为"已知的风格特征"而非问题。

## 7. 和现有门禁的配合

| 门禁 | 职责 | QGP 的辅助 |
|------|------|-----------|
| `anti_ai_guard` | 检查明显 AI 腔（总结腔、万能句式） | 提供 `abstract_summary_ratio`、`template_risk_ratio` |
| `padding_guard` | 检查凑字、重复、灌水 | 提供 `repeated_phrase_ratio`、`low_surprise_ratio` |
| `show_dont_tell_guard` | 检查"他终于明白"等禁用句式 | 提供 `abstract_summary_ratio`、`concrete_anchor_ratio` |
| `character_voice_guard` | 检查角色口吻差异 | 提供 `dialogue_variation_score` |
| `dialogue_beat_guard` | 检查对白节拍 | 提供句长变化辅助信号 |

QGP 是统计观察层，不替代任何现有门禁，只提供辅助信号。

## 8. 后端说明

### ngram 后端（默认）

- 纯 Python 标准库实现。
- 无需 GPU、无需联网、无需下载模型。
- 字符级 3-gram 统计 + 句长/节奏/密度分析。
- CI 友好，Windows/Linux/Mac 均可运行。

## 9. 不允许做的事

QGP 不实现以下功能：

- ❌ 输出 AI 率 / 人类率
- ❌ 输出平台检测通过率
- ❌ "困惑度越高越真人"
- ❌ "PPL 低于 X 就是 AI"
- ❌ 在 README 宣传"降低 AI 检测率""绕过平台审核"

QGP 的正确定位：

> QGP 用于辅助发现文本模板化、节奏过平、重复和异常混乱。

## 10. 相关文件

- `scripts/perplexity_quality_guard.py` — QGP 主门禁
- `scripts/qgp_baseline.py` — 基线构建工具
- `tests/test_perplexity_quality_guard.py` — 测试
- `config.example.json` → `qgp` 配置段
