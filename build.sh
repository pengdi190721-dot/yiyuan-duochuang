#!/usr/bin/env bash
# 校验技能格式并打包成 WorkBuddy 上传用的 ZIP：dist/yiyuan-duochuang.zip，并复制一份到 release/
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/validate_skill.py yiyuan-duochuang --zip dist
mkdir -p release
cp dist/yiyuan-duochuang.zip release/yiyuan-duochuang.zip
echo "上传用的 ZIP：release/yiyuan-duochuang.zip"
