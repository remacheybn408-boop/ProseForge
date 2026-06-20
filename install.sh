#!/usr/bin/env bash
# install.sh — HermesForgeN 安装器 (macOS / Linux)
# 用法: chmod +x install.sh && ./install.sh
set -e

PYTHON=${PYTHON:-python3}

echo "============================================"
VER=$(cat VERSION 2>/dev/null || echo "v0.8.0")
echo "  HermesForgeN $VER"
echo "  Hermes Plugin 安装 (Mac / Linux)"
echo "============================================"
echo ""

if ! command -v hermes >/dev/null 2>&1; then
  echo "[WARN] 'hermes' 命令未找到。请先安装 Hermes Agent:"
  echo "  https://hermes-agent.nousresearch.com/docs"
  echo ""
  echo "安装完成后重新运行本脚本。"
  exit 1
fi

echo "[STEP] 创建 writer profile（如尚未存在）..."
hermes profile create writer --clone 2>/dev/null || echo "  writer profile 已存在，跳过"

echo "[STEP] 安装插件到 writer profile..."
PLUGIN_SRC="hermes-plugin/hermes-forgen-engine"
PLUGIN_DST="$HOME/.hermes/profiles/writer/plugins/hermes-forgen-engine"

mkdir -p "$PLUGIN_DST"
cp -r "$PLUGIN_SRC/"* "$PLUGIN_DST/"

echo "[OK] 插件已安装到: $PLUGIN_DST"
echo ""
echo "============================================"
echo "  安装完成。"
echo ""
echo "  启动: hermes --profile writer"
echo "  工具: nf_状态  nf_预写  nf_续写  nf_改写 ..."
echo "============================================"
