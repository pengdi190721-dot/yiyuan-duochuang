#!/usr/bin/env bash
# 校验技能格式并打包成 WorkBuddy 上传用的 ZIP：dist/yiyuan-duochuang.zip
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/validate_skill.py yiyuan-duochuang --zip dist
