#!/usr/bin/env python3
"""install_plugin.py — 一键安装 hermes-forgen-engine 到 Hermes writer profile

用法:
    python install_plugin.py
    python install_plugin.py --profile writer

无需手动复制文件，脚本自动识别 Hermes 配置目录。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_hermes_root() -> Path:
    """自动发现 Hermes Agent 数据目录"""
    # 优先级: HERMES_DATA_DIR 环境变量 > ~/.hermes
    env = os.environ.get("HERMES_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".hermes"


def main():
    parser = argparse.ArgumentParser(description="安装 hermes-forgen-engine 插件到 Hermes profile")
    parser.add_argument("--profile", default="writer", help="目标 profile 名称 (默认: writer)")
    parser.add_argument("--plugin-src", default=None, help="插件源码目录 (默认: 项目内 hermes-plugin/hermes-forgen-engine)")
    args = parser.parse_args()

    # 项目根目录假定为脚本所在目录
    project_root = Path(__file__).resolve().parent
    plugin_src = Path(args.plugin_src) if args.plugin_src else project_root / "plugin" / "proseforge-Hermes"

    if not plugin_src.exists():
        print(f"[ERROR] 插件源码不存在: {plugin_src}")
        sys.exit(1)

    hermes_root = find_hermes_root()
    profile_dir = hermes_root / "profiles" / args.profile
    plugins_dir = profile_dir / "plugins"
    target_dir = plugins_dir / "proseforge-engine"

    if not profile_dir.exists():
        print(f"[ERROR] Hermes profile '{args.profile}' 不存在: {profile_dir}")
        print(f"  请先运行: hermes profile create {args.profile} --clone")
        sys.exit(1)

    # 创建 plugins 目录
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # 复制插件
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(plugin_src, target_dir)
    # 写入项目根路径标记，供 _find_proseforge_root() 读取
    (target_dir / ".project_root").write_text(str(project_root.resolve()), encoding="utf-8")
    print(f"[OK] 插件已安装到: {target_dir}")
    print(f"[OK] 已写入 .project_root: {project_root.resolve()}")

    # 确保 profile 配置加载该插件
    config_file = profile_dir / "config.yaml"
    if config_file.exists():
        ct = config_file.read_text(encoding="utf-8")
        if "proseforge-engine" not in ct:
            ct = ct.replace("plugins:", f"plugins:\n  enabled:\n    - proseforge-engine")
            config_file.write_text(ct, encoding="utf-8")
            print(f"[OK] 已在 config.yaml 中启用插件")

    print(f"\n启动: hermes --profile {args.profile}")
    print(f"工具: nf_状态  nf_预写  nf_续写  nf_改写  nf_流水  nf_卷管")


if __name__ == "__main__":
    main()
