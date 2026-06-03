#!/usr/bin/env python3
"""src/cli/commands_outline.py — CLI commands for novel-pipeline-write-engine v0.6.5"""

from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR, _get_outline_dir, _get_outline_manager
import sys
import json
from pathlib import Path
from datetime import datetime
from version import get_version
from config_utils import normalize_config, load_json_config, resolve_path

def cmd_outline(args):
    """大纲管理命令"""
    action = getattr(args, "outline_action", None)

    if action == "add":
        return _outline_add(getattr(args, "outline_file", ""),
                           getattr(args, "title", ""),
                           getattr(args, "genre", ""),
                           getattr(args, "style", ""),
                           replace_current=getattr(args, "replace_current", False),
                           keep_inactive=getattr(args, "keep_inactive", False),
                           dry_run=getattr(args, "dry_run", False))
    elif action == "import":
        return _outline_import(getattr(args, "outline_file", ""),
                              getattr(args, "title", ""),
                              getattr(args, "genre", ""),
                              getattr(args, "style", ""))
    elif action == "list":
        return _outline_list()
    elif action == "current":
        return _outline_current()
    elif action == "switch":
        return _outline_switch(getattr(args, "outline_id", ""))
    elif action == "diff":
        return _outline_diff(getattr(args, "id1", ""),
                            getattr(args, "id2", ""))
    elif action == "rollback":
        return _outline_rollback(getattr(args, "outline_id", ""))
    elif action == "compare":
        return _outline_compare(getattr(args, "compare_file", ""))
    elif action == "delete":
        return _outline_delete(getattr(args, "delete_id", ""))
    elif action == "undo":
        return _outline_undo()
    else:
        print("用法: python novel.py outline {add|import|list|current|switch|diff|rollback|compare|delete}")
        print()
        print("  add <文件>              添加大纲（自动相似度检测）")
        print("  import <文件> --title T  导入大纲（指定标题）")
        print("  list                    列出当前工作区所有大纲")
        print("  current                 显示当前激活大纲")
        print("  switch <id>             切换激活大纲")
        print("  diff <id1> <id2>        对比两个大纲")
        print("  rollback <id>           回滚大纲到上一版本")
        print("  compare <文件>           对比文件与当前激活大纲")
        print("  delete <id>             删除指定大纲")
        return 1


def _outline_add(file_path, title="", genre="", style="",
                  replace_current=False, keep_inactive=False, dry_run=False):
    """添加大纲文件 — P0-6/P0-7 智能行为"""
    # v0.6.5-clean7: 无文件时自动扫描 大纲/书名/大纲.txt
    if not file_path:
        nr = Path(_get_outline_dir())
        candidates = []
        if nr.exists():
            for subdir in sorted(nr.iterdir()):
                if subdir.is_dir():
                    of = subdir / "大纲.txt"
                    if of.exists():
                        candidates.append(of)
        if candidates:
            print(f"  📂 扫描 {nr} ...")
            print(f"  找到 {len(candidates)} 个大纲:")
            for i, c in enumerate(candidates, 1):
                try:
                    first = c.read_text(encoding="utf-8").strip().split("\n")[0].lstrip("# ")[:60]
                except Exception:
                    first = "(无法预览)"
                print(f"    [{i}] {c.parent.name}/大纲.txt")
                print(f"        {first}")
            print()
            print(f"  请输入编号 (1-{len(candidates)}) 或完整路径:")
            try:
                choice = input("  > ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    file_path = str(candidates[idx])
                    print(f"  已选择: {candidates[idx].parent.name}/大纲.txt")
                else:
                    file_path = choice
            except (ValueError, EOFError):
                file_path = choice
            if not file_path:
                print("  ❌ 未选择文件")
                return 1
        else:
            print(f"  💡 未找到大纲。请按此结构放置：")
            print(f"     {nr}/你的小说名/大纲.txt")
            return 1

    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    content = fp.read_text(encoding="utf-8")

    mgr = _get_outline_manager()

    # 如果已有激活大纲，做相似度检测
    current = mgr.current_outline()
    similarity = None
    if current:
        print("  检测到已有激活大纲，正在进行相似度分析...")
        try:
            from scripts.outline.similarity import OutlineSimilarity
            sim = OutlineSimilarity()
            similarity = sim.compare(
                title1=current.get("title", ""),
                title2=title or fp.stem,
                content1=current.get("content", ""),
                content2=content,
                genre1=current.get("genre", ""),
                genre2=genre,
                style1=current.get("style", ""),
                style2=style,
            )

            score = similarity["similarity_score"]
            cls_cn = {
                "high_similarity": "高相似度",
                "low_similarity": "低相似度",
                "uncertain": "不确定",
            }.get(similarity["classification"], similarity["classification"])

            rec_cn = {
                "upgrade": "建议升级（覆盖原大纲的新版本）",
                "same_novel": "可能是同一部小说",
                "new_novel": "可能是不同小说",
                "ask_user": "请人工确认",
            }.get(similarity["recommendation"], similarity["recommendation"])

            print(f"  📊 相似度得分: {score}/100  ({cls_cn})")
            print(f"  💡 建议: {rec_cn}")
            print()

            # 显示分类明细
            detail = similarity.get("detail", {})
            if detail.get("character_overlap"):
                co = detail["character_overlap"]
                print(f"    角色重叠: {co['score']}分 (共同角色: {', '.join(co['intersection']) if co['intersection'] else '无'})")
            if detail.get("worldbuilding_overlap"):
                wo = detail["worldbuilding_overlap"]
                print(f"    世界观重叠: {wo['score']}分 (共同关键词: {', '.join(wo['intersection'][:5]) if wo['intersection'] else '无'})")
            if detail.get("chapter_structure_similarity"):
                cs = detail["chapter_structure_similarity"]
                s1 = cs.get("outline1", {})
                s2 = cs.get("outline2", {})
                print(f"    章节结构: {cs['score']}分 (旧:{s1.get('chapters',0)}章/{s1.get('volumes',1)}卷 vs 新:{s2.get('chapters',0)}章/{s2.get('volumes',1)}卷)")

            print()

            # ── P0-6: 低相似度 (<35) — 自动创建新 slot ──
            if similarity["recommendation"] == "new_novel" or score < 35:
                print("  🔄 检测到可能是不同的小说。" if similarity["recommendation"] == "new_novel"
                      else "  🔄 相似度低于阈值，判定为新小说。")
                print()

                if dry_run:
                    print("  [--dry-run] 将执行以下操作:")
                    idle = mgr._find_idle_slot()
                    if idle:
                        print(f"  → 使用空闲 slot: {idle}")
                    else:
                        new_id = mgr._get_next_slot_id()
                        print(f"  → 创建新 slot: {new_id}")
                    print(f"  → 将大纲导入新 slot 并切换工作区" if title else f"  → 将「{fp.stem}」导入新 slot 并切换工作区" )
                    print(f"  → 原 slot 不受影响" )
                    print()
                    print("  使用 --replace-current 或 --keep-inactive 覆盖此行为。" )
                    return 0

                print("  → 正在为新小说创建独立工作区..." )
                result = mgr.add_outline_to_new_slot(
                    content=content,
                    title=title or "",
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                )

                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '创建失败')}" )
                    return 1

                print()
                print("=" * 60)
                print("  ✅ 新小说工作区创建成功！" )
                print("=" * 60)
                print(f"  新 Slot: {result['slot_id']}" )
                print(f"  创建方式: {'新建' if result['slot_created'] else '复用空闲 slot'}" )
                print(f"  大纲 ID: {result['outline_id']}" )
                print(f"  标题: {result['title']}" )
                print(f"  章节数: {result.get('chapter_count', 0)}" )
                if result.get('old_slot'):
                    print(f"  已从 {result['old_slot']} 切换到此工作区" )
                print()
                print("  使用 python novel.py db list 查看所有工作区" )
                return 0

            # ── P0-7: 高相似度 (>=70) — 升级当前大纲 ──
            if similarity["recommendation"] == "upgrade" or score >= 70:
                print("  📝 检测到这是当前小说的大纲升级版。" )

                if dry_run:
                    print(f"  [--dry-run] 相似度 {score}/100，判定为升级版。" )
                    print("  使用 --replace-current 激活为新大纲" )
                    print("  使用 --keep-inactive 保存但不激活" )
                    return 0

                if replace_current:
                    print("  → 正在替换当前激活大纲（旧版将保存为历史版本）..." )
                    result = mgr.add_outline_as_version(
                        content=content,
                        title=title or fp.stem,
                        genre=genre,
                        style=style,
                        similarity_result=similarity,
                        activate=True,
                    )
                elif keep_inactive:
                    print("  → 正在保存为独立大纲（不激活）..." )
                    result = mgr.add_outline_as_version(
                        content=content,
                        title=title or fp.stem,
                        genre=genre,
                        style=style,
                        similarity_result=similarity,
                        activate=False,
                    )
                else:
                    # 无 CLI flag: 询问用户
                    print("  检测到这是当前小说的大纲升级版。是否将它设为当前激活大纲？" )
                    print("  输入 y = 替换当前大纲（旧版保存为历史版本）" )
                    print("  输入 n = 保存但不激活（保留当前激活大纲）" )
                    try:
                        choice = input("  > ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        choice = "n"
                    if choice == "y" or choice == "yes":
                        print("  → 替换当前激活大纲..." )
                        result = mgr.add_outline_as_version(
                            content=content,
                            title=title or fp.stem,
                            genre=genre,
                            style=style,
                            similarity_result=similarity,
                            activate=True,
                        )
                    else:
                        print("  → 保存但不激活..." )
                        result = mgr.add_outline_as_version(
                            content=content,
                            title=title or fp.stem,
                            genre=genre,
                            style=style,
                            similarity_result=similarity,
                            activate=False,
                        )

                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1

                print()
                print("=" * 60)
                if result.get("mode") == "replace":
                    print("  ✅ 大纲已升级！（旧版已保存为历史版本）" )
                else:
                    print("  ✅ 大纲已保存（未激活，当前激活大纲不变）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                print(f"  章节数: {result.get('chapter_count', 0)}" )
                if result.get("versions_count", 0) > 0:
                    print(f"  历史版本: {result['versions_count']} 个" )
                if result.get("mode") == "inactive":
                    print()
                    print(f"  使用 python novel.py outline switch {result['id']} 激活此大纲" )
                print()
                return 0

            # ── 不确定区域 (35-69): ask_user ──
            print("  ⚠️  相似度处于不确定范围（35-69）。" )
            print("  请手动判断:" )
            print(f"    1 = 同一小说，替换当前大纲" )
            print(f"    2 = 同一小说，保存但不激活" )
            print(f"    3 = 不同小说，创建新工作区" )
            print(f"    4 = 取消" )
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "4"
            # v0.6.5-clean8: 支持 y/n/new/cancel 别名
            if choice in ("y", "yes", "1", "替换"):
                choice = "1"
            elif choice in ("n", "no", "2", "保存", "保留"):
                choice = "2"
            elif choice in ("new", "3", "新建"):
                choice = "3"
            elif choice in ("cancel", "c", "4", "取消"):
                choice = "4"
            if choice == "1":
                print("  → 替换当前激活大纲..." )
                result = mgr.add_outline_as_version(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                    activate=True,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 大纲已升级！（旧版保存为历史版本）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            elif choice == "2":
                print("  → 保存但不激活..." )
                result = mgr.add_outline_as_version(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                    activate=False,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 大纲已保存（未激活）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            elif choice == "3":
                print("  → 正在为新小说创建独立工作区..." )
                result = mgr.add_outline_to_new_slot(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '创建失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 新小说工作区创建成功！" )
                print("=" * 60)
                print(f"  新 Slot: {result['slot_id']}" )
                print(f"  大纲 ID: {result['outline_id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            else:
                print("  ⏭️  已取消。" )
                return 1

        except ImportError:
            print("  (相似度引擎不可用，跳过检测)" )
        except Exception as e:
            print(f"  (相似度检测异常: {e})" )

    # 无已有大纲或相似度引擎异常：直接添加
    result = mgr.add_outline(
        content=content,
        title=title,
        genre=genre,
        style=style,
        similarity_result=similarity,
    )

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '添加失败')}" )
        return 1

    print("=" * 60)
    print("  ✅ 大纲添加成功！" )
    print("=" * 60)
    print(f"  ID: {result['id']}" )
    print(f"  标题: {result['title']}" )
    print(f"  章节数: {result.get('chapter_count', 0)}" )
    print(f"  卷数: {result.get('volume_count', 1)}" )
    print()
    print("  使用 python novel.py outline list 查看所有大纲" )
    return 0


def _outline_import(file_path, title="", genre="", style=""):
    """导入大纲（指定标题）"""
    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    if not title:
        print("  ❌ 导入大纲必须指定标题: --title \"小说名称\"")
        return 1

    content = fp.read_text(encoding="utf-8")
    mgr = _get_outline_manager()

    result = mgr.import_outline(
        content=content,
        title=title,
        genre=genre,
        style=style,
    )

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '导入失败')}")
        return 1

    print("=" * 60)
    print("  ✅ 大纲导入成功！")
    print("=" * 60)
    print(f"  ID: {result['id']}")
    print(f"  标题: {result['title']}")
    print(f"  章节数: {result.get('chapter_count', 0)}")
    print()
    return 0


def _outline_list():
    """列出所有大纲，含版本关系显示"""
    mgr = _get_outline_manager()
    outlines = mgr.list_outlines()

    if not outlines:
        print("  当前工作区没有大纲。")
        print("  使用 python novel.py outline add <文件> 添加大纲。")
        return 0

    print("=" * 70)
    print("  大纲列表")
    print("=" * 70)
    print()

    for o in outlines:
        marker = "★" if o.get("active") else " "
        otype = o.get("type", "")
        type_labels = {
            "active": "🔵 当前使用",
            "historical": "📜 历史版本",
            "candidate": "📄 候选大纲",
        }
        type_label = type_labels.get(otype, otype)

        print(f"  {marker} [{o['id']}]  {type_label}")
        print(f"      标题: {o['title']}")
        print(f"      章节: {o.get('chapter_count', 0)} 章 / {o.get('volume_count', 1)} 卷")
        genre = o.get("genre", "")
        style = o.get("style", "")
        if genre or style:
            print(f"      类型/风格: {genre or '-'} / {style or '-'}")
        tags = o.get("tags", [])
        if tags:
            print(f"      标签: {', '.join(tags)}")

        # ── 版本关系 ──
        sv = o.get("source_version")
        if sv:
            print(f"      来源版本: v{sv.get('version', '?')}「{sv.get('title', '')}」({sv.get('saved_at', '')[:19] if sv.get('saved_at') else '未知时间'})")
        else:
            ver_count = o.get('versions_count', 0)
            print(f"      历史版本: {ver_count} 个")

        # ── 相似度 ──
        sim_score = o.get("similarity_score")
        if sim_score is not None:
            similar_to = o.get("similar_to", "")
            if similar_to:
                print(f"      相似度: {sim_score}% → 「{similar_to}」")
            else:
                print(f"      相似度: {sim_score}%")

        print(f"      更新时间: {o.get('updated_at', o.get('created_at', ''))[:19]}")
        print()

    active_count = sum(1 for o in outlines if o.get("type") == "active")
    historical_count = sum(1 for o in outlines if o.get("type") == "historical")
    candidate_count = sum(1 for o in outlines if o.get("type") == "candidate")
    print(f"  共 {len(outlines)} 个大纲：{active_count} 个使用中 / {historical_count} 个历史 / {candidate_count} 个候选")
    return 0


def _outline_current():
    """显示当前激活大纲"""
    mgr = _get_outline_manager()
    current = mgr.current_outline()

    if not current:
        print("  当前没有激活的大纲。")
        print("  使用 python novel.py outline add <文件> 添加大纲。")
        return 1

    print("=" * 60)
    print(f"  当前大纲: {current.get('title', '')}")
    print("=" * 60)
    print(f"  ID: {current.get('id', '')}")
    print(f"  章节数: {current.get('chapter_count', 0)}")
    print(f"  卷数: {current.get('volume_count', 1)}")
    genre = current.get("genre", "")
    style = current.get("style", "")
    if genre or style:
        print(f"  类型/风格: {genre or '-'} / {style or '-'}")
    tags = current.get("tags", [])
    if tags:
        print(f"  标签: {', '.join(tags)}")
    print(f"  版本数: {len(current.get('outline_versions', []))}")
    print(f"  创建时间: {current.get('created_at', '')[:19]}")
    print(f"  更新时间: {current.get('updated_at', '')[:19]}")

    # 相似度检测结果
    sc = current.get("similarity_check")
    if sc:
        cls_cn = {
            "high_similarity": "高相似度",
            "low_similarity": "低相似度",
            "uncertain": "不确定",
        }.get(sc.get("classification", ""), "")
        print()
        print(f"  相似度检测: {sc.get('similarity_score', 0)}/100 ({cls_cn})")

    print()
    print("-" * 60)
    print("  大纲内容预览（前30行）:")
    print("-" * 60)
    content = current.get("content", "")
    lines = content.strip().split("\n")[:30]
    for line in lines:
        print(f"  {line}")
    if len(content.strip().split("\n")) > 30:
        print(f"  ... (共 {len(content.strip().split(chr(10)))} 行)")
    print()

    return 0


def _outline_switch(outline_id):
    """切换激活大纲"""
    if not outline_id:
        print("用法: python novel.py outline switch <outline_id>")
        print("提示: 使用 python novel.py outline list 查看所有大纲ID")
        return 1

    mgr = _get_outline_manager()
    result = mgr.switch_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        available = result.get("available", [])
        if available:
            print(f"  可用大纲: {', '.join(available)}")
        return 1

    print(f"  ✅ 已切换到大纲: {result['title']}")
    print(f"  ID: {result['outline_id']}")
    prev = result.get("previous")
    if prev:
        print(f"  (之前: {prev})")
    return 0


def _outline_diff(id1, id2):
    """对比两个大纲"""
    if not id1 or not id2:
        print("用法: python novel.py outline diff <id1> <id2>")
        print("提示: 使用 python novel.py outline list 查看所有大纲ID")
        return 1

    mgr = _get_outline_manager()
    result = mgr.diff_outlines(id1, id2)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print("=" * 60)
    o1 = result.get("outline1", {})
    o2 = result.get("outline2", {})
    print(f"  大纲对比: [{o1.get('id', id1)}] {o1.get('title', '')}  vs  [{o2.get('id', id2)}] {o2.get('title', '')}")
    print("=" * 60)
    print()

    score = result["similarity_score"]
    cls_cn = {
        "high_similarity": "高相似度",
        "low_similarity": "低相似度",
        "uncertain": "不确定",
    }.get(result["classification"], result["classification"])

    rec_cn = {
        "upgrade": "建议升级（覆盖版本）",
        "same_novel": "可能是同一部小说",
        "new_novel": "可能是不同小说",
        "ask_user": "请人工确认",
    }.get(result["recommendation"], result["recommendation"])

    print(f"  📊 综合相似度: {score}/100")
    print(f"  🏷️  分类: {cls_cn}")
    print(f"  💡 建议: {rec_cn}")
    print()

    detail = result.get("detail", {})
    print("  各维度明细:")
    print("  " + "-" * 50)

    # 标题
    ts = detail.get("title_similarity", {})
    print(f"  标题相似度:      {ts.get('score', 0)}分  (权重{ts.get('weight', 0)*100:.0f}%)")
    print(f"    \"{ts.get('title1', '')}\" ↔ \"{ts.get('title2', '')}\"")

    # 角色
    co = detail.get("character_overlap", {})
    print(f"  角色名重叠:      {co.get('score', 0)}分  (权重{co.get('weight', 0)*100:.0f}%)")
    print(f"    大纲1角色: {', '.join(co.get('chars1', [])) or '(无)'}")
    print(f"    大纲2角色: {', '.join(co.get('chars2', [])) or '(无)'}")
    common_chars = co.get("intersection", [])
    print(f"    共同角色: {', '.join(common_chars) if common_chars else '(无)'}")

    # 世界观
    wo = detail.get("worldbuilding_overlap", {})
    print(f"  世界观重叠:      {wo.get('score', 0)}分  (权重{wo.get('weight', 0)*100:.0f}%)")
    common_world = wo.get("intersection", [])
    print(f"    共同关键词: {', '.join(common_world[:10]) if common_world else '(无)'}")

    # 章节结构
    cs = detail.get("chapter_structure_similarity", {})
    print(f"  章节结构相似:    {cs.get('score', 0)}分  (权重{cs.get('weight', 0)*100:.0f}%)")
    s1 = cs.get("outline1", {})
    s2 = cs.get("outline2", {})
    print(f"    大纲1: {s1.get('chapters', 0)}章/{s1.get('volumes', 1)}卷")
    print(f"    大纲2: {s2.get('chapters', 0)}章/{s2.get('volumes', 1)}卷")

    # 类型/风格
    gs = detail.get("genre_style_overlap", {})
    print(f"  题材/风格重叠:   {gs.get('score', 0)}分  (权重{gs.get('weight', 0)*100:.0f}%)")
    g_ol = gs.get("genre_overlap", [])
    s_ol = gs.get("style_overlap", [])
    print(f"    共同题材: {', '.join(g_ol) if g_ol else '(无)'}")
    print(f"    共同风格: {', '.join(s_ol) if s_ol else '(无)'}")

    print()
    return 0


def _outline_rollback(outline_id):
    """回滚大纲"""
    if not outline_id:
        print("用法: python novel.py outline rollback <outline_id>")
        return 1

    mgr = _get_outline_manager()
    result = mgr.rollback_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print(f"  ✅ 已回滚大纲「{result['title']}」到版本 {result['rolled_back_to']}")
    print(f"  保存时间: {result.get('saved_at', '')[:19]}")
    print(f"  剩余历史版本: {result.get('versions_remaining', 0)}")
    return 0


def _outline_compare(file_path):
    """对比文件与当前大纲"""
    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    mgr = _get_outline_manager()
    result = mgr.compare_with_file(file_path)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print("=" * 60)
    o1 = result.get("outline1", {})
    o2 = result.get("outline2", {})
    print(f"  大纲对比: [{o1.get('id', '')}] {o1.get('title', '')}  vs  文件 {o2.get('title', '')}")
    print("=" * 60)
    print()

    score = result["similarity_score"]
    cls_cn = {
        "high_similarity": "高相似度",
        "low_similarity": "低相似度",
        "uncertain": "不确定",
    }.get(result["classification"], result["classification"])

    rec_cn = {
        "upgrade": "可能是当前大纲的新版本",
        "same_novel": "可能是同一部小说",
        "new_novel": "可能是不同小说",
        "ask_user": "请人工确认",
    }.get(result["recommendation"], result["recommendation"])

    print(f"  📊 综合相似度: {score}/100")
    print(f"  🏷️  分类: {cls_cn}")
    print(f"  💡 建议: {rec_cn}")
    print()

    detail = result.get("detail", {})
    print("  各维度明细:")
    print("  " + "-" * 50)
    ts = detail.get("title_similarity", {})
    print(f"  标题相似度:      {ts.get('score', 0)}分")
    co = detail.get("character_overlap", {})
    print(f"  角色名重叠:      {co.get('score', 0)}分")
    common_chars = co.get("intersection", [])
    if common_chars:
        print(f"    共同角色: {', '.join(common_chars)}")
    wo = detail.get("worldbuilding_overlap", {})
    print(f"  世界观重叠:      {wo.get('score', 0)}分")
    common_world = wo.get("intersection", [])
    if common_world:
        print(f"    共同关键词: {', '.join(common_world[:10])}")
    cs = detail.get("chapter_structure_similarity", {})
    print(f"  章节结构相似:    {cs.get('score', 0)}分")
    gs = detail.get("genre_style_overlap", {})
    print(f"  题材/风格重叠:   {gs.get('score', 0)}分")
    print()
    return 0


def _outline_delete(outline_id):
    """删除大纲"""
    if not outline_id:
        print("用法: python novel.py outline delete <outline_id>")
        return 1

    mgr = _get_outline_manager()
    result = mgr.delete_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print(f"  ✅ 已删除大纲「{result.get('title', outline_id)}」")
    new_active = result.get("new_active")
    if new_active:
        print(f"  ℹ️  激活大纲已自动切换为: {new_active}")
    elif new_active is None and result.get("new_active") is not None:
        print(f"  ⚠️  当前工作区已无大纲，请添加新大纲。")
    return 0


def _outline_undo():
    """v0.6.5-clean7: 撤销最近一次 outline add"""
    mgr = _get_outline_manager()
    result = mgr.undo_last_add()
    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1
    print(f"  ✅ {result.get('message', '')}")
    return 0


# ═══════════════════════════════════════════════════════════════
#  scc-help — 中文用户手册
# ═══════════════════════════════════════════════════════════════
