#!/usr/bin/env python3
"""
chief_editor.py — 主编汇总Agent v0.5.5

汇总所有 Agent 报告:
  - 去重: 相同/相似 finding 合并
  - 排序: 按严重度 (FAIL > WARN > PASS)
  - 分类: must_fix / should_fix / keep
  - 输出整体评分和建议

不调用外部LLM, 纯规则引擎。
"""

import re
from collections import Counter
from .base_agent import BaseAgent


class ChiefEditor(BaseAgent):
    """主编汇总审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="chief_editor", config=config)
        self.dedup_threshold = self.config.get("dedup_threshold", 0.6)
        self.must_fix_threshold = self.config.get("must_fix_threshold", 70)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        """汇总所有 agent 报告。

        Args:
            content: 原文章节 (chief_editor 不直接分析文本).
            chapter_no: 章节号.
            context: 必须包含 'agent_results' — 其他 agent 的 review 返回列表.

        Returns:
            汇总报告 dict.
        """
        context = context or {}
        agent_results = context.get("agent_results", [])

        if not agent_results:
            return self._build_result(0, "PASS", [{
                "level": "PASS",
                "message": "无 Agent 报告可汇总",
                "evidence": "",
                "suggestion": "确保 orchestrator 正确调度了 Agent"
            }])

        return self._compile(chapter_no, agent_results)

    def _compile(self, chapter_no: int, agent_results: list) -> dict:
        """编译汇总报告"""
        # ── 收集所有 findings ──
        all_findings = []
        agent_statuses = []
        agent_scores = []

        for result in agent_results:
            agent_statuses.append(result.get("status", "PASS"))
            agent_scores.append(result.get("score", 0))
            for f in result.get("findings", []):
                f["_agent"] = result.get("agent", "unknown")
                all_findings.append(f)

        # ── 去重 ──
        deduped = self._deduplicate(all_findings)

        # ── 分类 ──
        must_fix = []
        should_fix = []
        keep = []

        for f in deduped:
            level = f.get("level", "WARN")
            agents_tagged = f.get("_agents", [f.get("_agent", "unknown")])
            agent_count = len(set(agents_tagged))

            if level == "FAIL":
                must_fix.append(f)
            elif level == "WARN" and agent_count >= 2:
                # 多个 agent 都报的 WARN → must_fix
                must_fix.append(f)
            elif level == "WARN":
                should_fix.append(f)
            else:
                keep.append(f)

        # ── 排序: must_fix 先按严重度再按 Agent 数 ──
        must_fix.sort(key=lambda x: (
            0 if x.get("level") == "FAIL" else 1,
            -len(set(x.get("_agents", [])))
        ))
        should_fix.sort(key=lambda x: -len(set(x.get("_agents", []))))

        # ── 计算整体分数 ──
        overall_score = self._compute_overall(agent_scores, agent_statuses,
                                               must_fix, should_fix)

        # ── 整体状态 ──
        fail_count = sum(1 for s in agent_statuses if s == "FAIL")
        warn_count = sum(1 for s in agent_statuses if s == "WARNING")
        pass_count = sum(1 for s in agent_statuses if s == "PASS")

        if fail_count > 0:
            overall_status = "FAIL"
        elif warn_count >= 3:
            overall_status = "WARNING"
        elif overall_score >= 70:
            overall_status = "WARNING"
        else:
            overall_status = "PASS"

        # ── 构建 findings ──
        chief_findings = []

        # 摘要
        chief_findings.append({
            "level": overall_status,
            "message": f"审稿团汇总: {pass_count} PASS / {warn_count} WARNING / {fail_count} FAIL",
            "evidence": f"总评分: {overall_score}/100",
            "suggestion": self._build_suggestion(overall_status, must_fix, should_fix),
        })

        # must_fix
        for f in must_fix:
            chief_findings.append({
                "level": "FAIL",
                "message": f"[must_fix] ({', '.join(set(f.get('_agents', [])))}) {f.get('message', '')}",
                "evidence": f.get("evidence", ""),
                "suggestion": f.get("suggestion", ""),
            })

        # should_fix (前5条)
        for f in should_fix[:5]:
            chief_findings.append({
                "level": "WARN",
                "message": f"[should_fix] ({', '.join(set(f.get('_agents', [])))}) {f.get('message', '')}",
                "evidence": f.get("evidence", ""),
                "suggestion": f.get("suggestion", ""),
            })

        # ── Agent 分数明细 ──
        agent_score_details = {}
        for result in agent_results:
            agent_score_details[result.get("agent", "?")] = {
                "score": result.get("score", 0),
                "status": result.get("status", "PASS"),
                "finding_count": len(result.get("findings", [])),
            }

        return {
            "agent": self.name,
            "chapter": chapter_no,
            "score": overall_score,
            "status": overall_status,
            "findings": chief_findings,
            "summary": {
                "pass_count": pass_count,
                "warn_count": warn_count,
                "fail_count": fail_count,
                "must_fix_count": len(must_fix),
                "should_fix_count": len(should_fix),
                "keep_count": len(keep),
            },
            "agent_scores": agent_score_details,
            "must_fix": [self._strip_meta(f) for f in must_fix],
            "should_fix": [self._strip_meta(f) for f in should_fix],
            "keep": [self._strip_meta(f) for f in keep],
        }

    def _deduplicate(self, findings: list) -> list:
        """去重: 合并相似 finding"""
        if not findings:
            return []

        groups = []
        used = set()

        for i, f1 in enumerate(findings):
            if i in used:
                continue
            group = [f1]
            used.add(i)
            msg1 = f1.get("message", "")

            for j, f2 in enumerate(findings):
                if j in used:
                    continue
                msg2 = f2.get("message", "")
                similarity = self._text_similarity(msg1, msg2)
                if similarity >= self.dedup_threshold:
                    group.append(f2)
                    used.add(j)

            groups.append(group)

        # 合并每组
        merged = []
        for group in groups:
            base = dict(group[0])
            agents = list(set(f.get("_agent", "?") for f in group))
            base["_agents"] = agents
            base["_count"] = len(group)
            if len(group) > 1:
                base["message"] = f"[{len(group)}个Agent报告] {base.get('message', '')}"
            merged.append(base)

        return merged

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """简单文本相似度 (基于共同词)"""
        def tokenize(s):
            return set(re.findall(r'[\u4e00-\u9fff]{1,3}', s))
        ta = tokenize(a)
        tb = tokenize(b)
        if not ta or not tb:
            return 0.0
        intersection = ta & tb
        union = ta | tb
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _compute_overall(scores: list, statuses: list,
                         must_fix: list, should_fix: list) -> int:
        """计算整体分数 (0=完美, 100=极差)"""
        if not scores:
            return 0

        avg_score = sum(scores) / len(scores)

        # must_fix 加权
        must_fix_penalty = len(must_fix) * 8
        should_fix_penalty = len(should_fix) * 3

        # FAIL 加权
        fail_penalty = sum(20 for s in statuses if s == "FAIL")
        warn_penalty = sum(5 for s in statuses if s == "WARNING")

        total = avg_score * 0.5 + must_fix_penalty + should_fix_penalty + \
                fail_penalty + warn_penalty
        return min(100, int(total))

    @staticmethod
    def _strip_meta(finding: dict) -> dict:
        """去掉内部元数据字段"""
        return {
            "level": finding.get("level", ""),
            "message": finding.get("message", ""),
            "evidence": finding.get("evidence", ""),
            "suggestion": finding.get("suggestion", ""),
        }

    @staticmethod
    def _build_suggestion(status: str, must_fix: list,
                          should_fix: list) -> str:
        """生成修改建议摘要"""
        parts = []
        if must_fix:
            parts.append(f"必须修复{len(must_fix)}项严重问题")
        if should_fix:
            parts.append(f"建议修复{len(should_fix)}项")
        if status == "PASS":
            parts.append("整体质量良好, 保持当前水准")
        elif status == "FAIL":
            parts.append("建议大幅修订后再提交")
        return "; ".join(parts) if parts else "无需修改"
