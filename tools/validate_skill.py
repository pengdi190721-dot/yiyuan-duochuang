#!/usr/bin/env python3
"""校验技能目录是否符合 WorkBuddy 技能包格式，并可打包成上传用的 ZIP。

用法：
  python3 tools/validate_skill.py yiyuan-duochuang            # 只校验
  python3 tools/validate_skill.py yiyuan-duochuang --zip dist  # 校验并打包为 dist/yiyuan-duochuang.zip

校验项（与 WorkBuddy 技能市场上传规范一致）：
  - SKILL.md 以 YAML frontmatter 开头，只含受支持的顶层字段，不重复
  - 必填且非空：name、display_name、display_name_en、description、description_zh、
    description_en、category、version、author、allowed-tools
  - name 等于目录名，小写 kebab-case；version 为语义化版本；category 为小写标识符
  - display_name / display_name_en ≤ 64 字符；三个 description ≤ 1200 字符
  - allowed-tools 只能是 Bash、Read、Write、Glob、Grep，且不重复
  - SKILL.md 正文 ≤ 5000 词（中文按字计）
  - 正文里 @references/… 和 @templates/… 指向的文件都存在
  - ZIP 根目录为技能目录，不含符号链接、越界路径和缓存文件
  - 只含纯文本文件（.md .py .js .txt .json .yaml .yml），不超过 300 个文件、10 MB
"""
from __future__ import annotations

import argparse
import pathlib
import re
import stat
import sys
import zipfile

REQUIRED = {"name", "display_name", "display_name_en", "description", "description_zh",
            "description_en", "category", "version", "author", "allowed-tools"}
ALLOWED_TOOLS = {"Bash", "Read", "Write", "Glob", "Grep"}
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
EXCLUDE_PARTS = {"__pycache__", ".DS_Store"}
# WorkBuddy / CodeBuddy 技能包只接受纯文本文件，没有扩展名的文件（如 LICENSE）也会被拒绝
ALLOWED_EXT = {".md", ".py", ".js", ".txt", ".json", ".yaml", ".yml"}
MAX_FILES, MAX_BYTES = 300, 10 * 1024 * 1024


def parse_frontmatter(text: str, path: pathlib.Path) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        sys.exit(f"{path}: 缺少 YAML frontmatter")
    lines, values, i = m.group(1).splitlines(), {}, 0
    while i < len(lines):
        line = lines[i]
        mm = re.fullmatch(r"([a-z][a-z0-9_-]*):(?:[ \t]*(.*))?", line)
        if not mm:
            sys.exit(f"{path}: frontmatter 第 {i + 2} 行不是受支持的顶层字段")
        key, value = mm.groups()
        if key in values:
            sys.exit(f"{path}: frontmatter 字段重复 {key}")
        if value in {">", "|"}:
            block = []
            i += 1
            while i < len(lines) and (not lines[i] or lines[i][0].isspace()):
                if lines[i]:
                    if not lines[i].startswith("  "):
                        sys.exit(f"{path}: {key} 多行内容必须缩进两个空格")
                    block.append(lines[i][2:])
                i += 1
            values[key] = "\n".join(block).strip()
            continue
        values[key] = (value or "").strip()
        i += 1
    return values, text[m.end():]


def validate(skill: pathlib.Path) -> None:
    path = skill / "SKILL.md"
    if not path.is_file():
        sys.exit(f"{skill}: 缺少 SKILL.md")
    values, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)
    missing = sorted(REQUIRED - values.keys())
    if missing:
        sys.exit(f"{path}: frontmatter 缺字段 {', '.join(missing)}")
    empty = sorted(k for k in REQUIRED if not values[k])
    if empty:
        sys.exit(f"{path}: frontmatter 字段不能为空 {', '.join(empty)}")
    if values["name"] != skill.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["name"]):
        sys.exit(f"{path}: name 必须等于目录名且使用小写 kebab-case")
    if not SEMVER.fullmatch(values["version"]):
        sys.exit(f"{path}: version 必须为语义化版本")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", values["category"]):
        sys.exit(f"{path}: category 必须为小写标识符")
    for key in ("display_name", "display_name_en"):
        if len(values[key]) > 64:
            sys.exit(f"{path}: {key} 超过 64 字符")
    for key in ("description", "description_zh", "description_en"):
        if len(values[key]) > 1200:
            sys.exit(f"{path}: {key} 超过 1200 字符（现在 {len(values[key])}）")
    tools = [t.strip() for t in values["allowed-tools"].split(",") if t.strip()]
    unknown = sorted(set(tools) - ALLOWED_TOOLS)
    if not tools or len(tools) != len(set(tools)) or unknown:
        sys.exit(f"{path}: allowed-tools 无效或重复 {', '.join(unknown)}")
    words = len(re.findall(r"[一-鿿]", body)) + len(re.findall(r"[A-Za-z0-9_]+", body))
    if words > 5000:
        sys.exit(f"{path}: 正文 {words} 词，超过 5000，细节请移到 references/")
    for ref in sorted(set(re.findall(r"@((?:references|templates|scripts)/[\w./-]+)", body))):
        if not (skill / ref).exists():
            sys.exit(f"{path}: 引用的文件不存在 {ref}")
    files = [p for p in skill.rglob("*") if p.is_file() and not (EXCLUDE_PARTS & set(p.parts)) and p.suffix != ".pyc"]
    for p in skill.rglob("*"):
        if p.is_symlink():
            sys.exit(f"{p}: 技能目录里不能有符号链接")
    bad = sorted(str(p.relative_to(skill)) for p in files if p.suffix.lower() not in ALLOWED_EXT)
    if bad:
        sys.exit(f"不允许的文件类型（只接受 {' '.join(sorted(ALLOWED_EXT))}）：{', '.join(bad)}")
    if len(files) > MAX_FILES:
        sys.exit(f"文件数 {len(files)} 超过 {MAX_FILES}")
    total = sum(p.stat().st_size for p in files)
    if total > MAX_BYTES:
        sys.exit(f"总大小 {total // 1024} KB 超过 10 MB")
    print(f"frontmatter ok · 正文约 {words} 词 · 引用文件齐全 · {skill.name}")


def build_zip(skill: pathlib.Path, dist: pathlib.Path) -> pathlib.Path:
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"{skill.name}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(skill.rglob("*")):
            if p.is_dir() or EXCLUDE_PARTS & set(p.parts) or p.suffix == ".pyc":
                continue
            zf.write(p, f"{skill.name}/{p.relative_to(skill).as_posix()}")
    prefix = f"{skill.name}/"
    with zipfile.ZipFile(out) as zf:
        names = {e.filename for e in zf.infolist()}
        if f"{prefix}SKILL.md" not in names:
            sys.exit(f"{out}: 缺少 {prefix}SKILL.md")
        for e in zf.infolist():
            parts = pathlib.PurePosixPath(e.filename).parts
            if (not e.filename.startswith(prefix) or e.filename.startswith("/") or ".." in parts
                    or "\\" in e.filename or stat.S_ISLNK(e.external_attr >> 16)):
                sys.exit(f"{out}: 不安全或越界条目 {e.filename}")
        bad = zf.testzip()
        if bad:
            sys.exit(f"{out}: 压缩内容损坏 {bad}")
        count = len(names)
    print(f"已打包 {out}（{count} 个文件，{out.stat().st_size // 1024} KB）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--zip", metavar="DIST", help="校验通过后打包到这个目录")
    args = ap.parse_args()
    skill = pathlib.Path(args.skill_dir).resolve()
    validate(skill)
    if args.zip:
        build_zip(skill, pathlib.Path(args.zip))
    return 0


if __name__ == "__main__":
    sys.exit(main())
