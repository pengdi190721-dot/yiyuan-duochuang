#!/usr/bin/env python3
"""检查各平台 post.json：字数、禁用词、硬信息、出图字段、图片规格、AI 标识、平台间重复、照抄对标。

用法：
  python3 lint.py --run "输出/2026-11-23_主题" --platform xiaohongshu   # 只查一个平台（也会和已有的其他平台比重复）
  python3 lint.py --run "输出/2026-11-23_主题"                          # 查全部平台
结果写进输出目录的 06_审核报告.md；有 FAIL 时退出码为 1。
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PLATFORMS, REFERENCES, TARGET_PX, TEMPLATES, TEXT_MODES, char_count, check_platform,
    data_dir, existing_platforms, get_path, iter_publishable, load_json, now, platform_dir,
    post_path, ratio_value, resolve_file, safe_name, save_json, selected_images, workbench_dir,
)

NUM_PATTERNS = [
    r"\d{3,}(?:,\d{3})*(?:\.\d+)?",
    r"\d{1,2}[:：]\d{2}",
    r"\d+(?:\.\d+)?\s*(?:元|块|%|％|折|平方米|平米|㎡|公里|km|分钟|小时|米)",
]
BOOKING_WORDS = re.compile(r"预订|预定|下单|购买|订房|小程序|购票|抢购")
PRICE_RE = re.compile(r"\d+(?:\.\d+)?\s*元")
SENTENCE_SPLIT = re.compile(r"[。！？!?\n]")


class Report:
    def __init__(self) -> None:
        self.items: dict[str, list[str]] = {"FAIL": [], "WARN": [], "INFO": []}

    def add(self, level: str, msg: str) -> None:
        if msg not in self.items[level]:
            self.items[level].append(msg)

    def as_dict(self) -> dict:
        return {k.lower(): v for k, v in self.items.items()}


# ---------- 禁用词 ----------

def load_banned(brand_md: pathlib.Path | None) -> list[dict]:
    groups: list[dict] = []
    current: dict | None = None
    for raw in (REFERENCES / "banned_words.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[(\S+)\s+level=(FAIL|WARN)\s+platforms=(\S+)\]", line)
        if header:
            name, level, plats = header.groups()
            current = {"name": name, "level": level,
                       "platforms": None if plats == "all" else set(plats.split(",")), "terms": []}
            groups.append(current)
            continue
        if current is not None:
            current["terms"].append(line)
    if brand_md and brand_md.is_file():
        text = brand_md.read_text(encoding="utf-8")
        m = re.search(r"^## 禁用词\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if m:
            terms = []
            for raw in m.group(1).splitlines():
                word = raw.strip().lstrip("-*").strip()
                if word and not word.startswith("<!--") and "【待填" not in word:
                    terms.append(word)
            if terms:
                groups.append({"name": "品牌禁用词", "level": "FAIL", "platforms": None, "terms": terms})
    return groups


def term_hits(term: str, text: str) -> list[str]:
    if term.startswith("re:"):
        return [m.group(0) for m in re.finditer(term[3:], text)]
    return [term] if term in text else []


def check_banned(code: str, post: dict, groups: list[dict], rep: Report) -> None:
    for field, text in iter_publishable(post):
        for group in groups:
            if group["platforms"] is not None and code not in group["platforms"]:
                continue
            for term in group["terms"]:
                for hit in term_hits(term, text):
                    if group["level"] == "WARN":
                        rep.add("WARN", f"{field}：命中\"{group['name']}\"词「{hit}」，没有具体内容支撑就按去 AI 味清单改")
                    else:
                        rep.add("FAIL", f"{field}：命中\"{group['name']}\"词「{hit}」")


# ---------- 字数 ----------

def lines_of(text: str) -> list[str]:
    return [p for p in re.split(r"[｜|\n]", text) if p.strip()]


def check_limits(code: str, post: dict, rep: Report) -> None:
    limits = load_json(TEMPLATES / f"{code}_post.json").get("_limits", {})
    for field, rule in limits.items():
        if field in ("images", "on_image_text"):
            continue
        value = get_path(post, field)
        if "count" in rule:
            lo, hi = rule["count"]
            n = len(value) if isinstance(value, list) else 0
            if not isinstance(value, list):
                rep.add("FAIL", f"{field}：应为列表，共 {lo}–{hi} 项")
            elif not lo <= n <= hi:
                rep.add("FAIL", f"{field}：现在 {n} 项，要求 {lo}–{hi} 项")
        texts = value if isinstance(value, list) else [value]
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                continue
            label = f"{field}[{i}]" if isinstance(value, list) else field
            n = char_count(text)
            if "chars" in rule:
                lo, hi = rule["chars"]
                if n == 0 and lo > 0:
                    rep.add("FAIL", f"{label}：为空")
                elif n and not lo <= n <= hi:
                    rep.add("FAIL", f"{label}：{n} 字，要求 {lo}–{hi} 字")
            if "warn_chars" in rule and n:
                lo, hi = rule["warn_chars"]
                if not lo <= n <= hi:
                    rep.add("WARN", f"{label}：{n} 字，建议 {lo}–{hi} 字")
    img_rule = limits.get("images", {})
    sel = selected_images(post)
    if "count" in img_rule:
        lo, hi = img_rule["count"]
        if not lo <= len(sel) <= hi:
            rep.add("FAIL", f"images：选中 {len(sel)} 张，要求 {lo}–{hi} 张（原图不够时在交互点 A 问用户补图或合并）")
    text_rule = limits.get("on_image_text")
    if text_rule:
        for i, img in enumerate(sel):
            text = img.get("on_image_text") or ""
            parts = lines_of(text)
            if len(parts) > text_rule["lines"]:
                rep.add("FAIL", f"images[{i}].on_image_text：{len(parts)} 行，最多 {text_rule['lines']} 行（用｜分行）")
            for part in parts:
                if char_count(part) > text_rule["line_chars"]:
                    rep.add("FAIL", f"images[{i}].on_image_text：「{part}」{char_count(part)} 字，每行最多 {text_rule['line_chars']} 字")


# ---------- 出图字段 ----------

def check_image_fields(post: dict, run: pathlib.Path, rep: Report) -> None:
    for i, img in enumerate(selected_images(post)):
        slot = img.get("slot") or f"#{i}"
        if img.get("ratio") not in TARGET_PX:
            rep.add("FAIL", f"图片「{slot}」：ratio「{img.get('ratio')}」不在尺寸表里（可选 {', '.join(TARGET_PX)}）")
        if img.get("text_mode") not in TEXT_MODES:
            rep.add("FAIL", f"图片「{slot}」：text_mode 只能是 {' / '.join(TEXT_MODES)}")
        if img.get("text_mode") == "底图叠字" and not img.get("text_layers"):
            rep.add("FAIL", f"图片「{slot}」：底图叠字必须填 text_layers")
        refs = img.get("reference_images") or []
        for ref in refs:
            if resolve_file(ref, run) is None:
                rep.add("FAIL", f"图片「{slot}」：找不到参考原图「{ref}」")
        if refs and not (img.get("keep") or "").strip():
            rep.add("FAIL", f"图片「{slot}」：有参考原图时必须填 keep（必须保留的真实元素）")
        if not refs:
            rep.add("WARN", f"图片「{slot}」：没有参考原图，只适合做纯信息卡，不能用来表现实景")


# ---------- 硬信息 ----------

def norm_num(s: str) -> str:
    return s.replace(",", "").replace("：", ":").replace("％", "%")


def check_facts(post: dict, card: dict | None, rep: Report) -> None:
    if card is None:
        rep.add("FAIL", "找不到 00_内容卡.json，无法核对硬信息")
        return
    card_text = norm_num(json.dumps(card, ensure_ascii=False))
    card_text = re.sub(r"\s", "", card_text)
    seen: set[tuple[str, str]] = set()
    for field, text in iter_publishable(post):
        for pat in NUM_PATTERNS:
            for m in re.finditer(pat, text):
                num = re.sub(r"\s", "", norm_num(m.group(0)))
                digits = re.match(r"[\d.:]+", num)
                key = digits.group(0) if digits else num
                if key and key not in card_text and (field, key) not in seen:
                    seen.add((field, key))
                    rep.add("FAIL", f"{field}：数字「{m.group(0)}」不在内容卡里，可能是编造的")
        for m in re.finditer(r"【待补[^】]*】", text):
            rep.add("INFO", f"{field}：占位 {m.group(0)}，交付前需要用户补上")


def check_declarations(code: str, post: dict, rep: Report) -> None:
    decl = post.get("declarations") or {}
    if selected_images(post) and decl.get("ai_generated") is not True:
        rep.add("FAIL", "有 AI 生成图片，但 declarations.ai_generated 不是 true")
    joined = "\n".join(t for _, t in iter_publishable(post))
    if PRICE_RE.search(joined) and BOOKING_WORDS.search(joined):
        rep.add("WARN", "稿件同时含价格和预订方式：属于带购买方式的推广内容，在交互点 B 确认标\"广告\"或勾选营销推广声明")


# ---------- 照抄对标 ----------

def longest_common(a: str, b: str) -> str:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    m = sm.find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size]


def _breakdown_texts(paths) -> list[str]:
    out: list[str] = []
    for path in paths:
        try:
            data = load_json(path)
        except Exception:
            continue
        for block in (data.get("text_blocks") or []) if isinstance(data, dict) else []:
            text = (block or {}).get("text") or ""
            if text and text != "unknown":
                out.append(re.sub(r"\s", "", text))
    return out


def _sample_texts(paths) -> list[str]:
    """风格库里用户喜欢的文案：取"## 原文"一节。"""
    out: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^## 原文\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        body = re.sub(r"\s", "", m.group(1) if m else "")
        if body:
            out.append(body)
    return out


def check_benchmark_copy(code: str, post: dict, run: pathlib.Path, wb: pathlib.Path, rep: Report) -> None:
    """对标图原文（别人的内容）连续 8 字相同为 FAIL；用户喜欢的文案样本连续 12 字相同为 WARN。"""
    lib = wb / "风格库"
    bench = _breakdown_texts(sorted(run.glob("00_对标拆解*.json")) + sorted((lib / "图片").glob("**/*.json")))
    samples = _sample_texts(sorted((lib / "文案" / code).glob("*.md")) + sorted((lib / "文案" / "通用").glob("*.md")))
    if not bench and not samples:
        return
    for field, text in iter_publishable(post):
        flat = re.sub(r"\s", "", text)
        for bt in bench:
            common = longest_common(flat, bt)
            if len(common) >= 8:
                rep.add("FAIL", f"{field}：与对标图原文连续 {len(common)} 字相同「{common}」，属于照抄")
        for st in samples:
            common = longest_common(flat, st)
            if len(common) >= 12:
                rep.add("WARN", f"{field}：与风格库文案样本连续 {len(common)} 字相同「{common[:20]}…」，只学写法，换成这次的内容")


# ---------- 图片文件 ----------

def check_image_files(code: str, post: dict, run: pathlib.Path, rep: Report) -> None:
    img_dir = platform_dir(run, code) / "图片"
    files = sorted(p for p in img_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if img_dir.is_dir() else []
    sel = selected_images(post)
    if not files:
        if sel:
            rep.add("INFO", "图片还没生成（第 ⑦ 步之后再查图片规格）")
        return
    try:
        from PIL import Image
    except ImportError:
        rep.add("WARN", "没装 Pillow，跳过图片规格检查（python3 -m pip install pillow）")
        return
    by_slot = {safe_name(str(img.get("slot"))): img for img in sel}
    seen = set()
    for path in files:
        m = re.match(r"\d+_(.+)$", path.stem)
        slot = m.group(1) if m else path.stem
        img = by_slot.get(slot)
        if img is None:
            rep.add("WARN", f"图片文件「{path.name}」在 post.json 里没有对应的选中项")
            continue
        seen.add(slot)
        with Image.open(path) as im:
            w, h = im.size
        want = img.get("ratio")
        if want in TARGET_PX:
            if abs(w / h - ratio_value(want)) / ratio_value(want) > 0.015:
                rep.add("FAIL", f"图片「{path.name}」：比例 {w}×{h} 与要求的 {want} 不符")
            tw, th = TARGET_PX[want]
            if w < tw or h < th:
                rep.add("WARN", f"图片「{path.name}」：{w}×{h} 小于平台建议的 {tw}×{th}，母版图分辨率不够")
    for slot in by_slot:
        if slot not in seen:
            rep.add("INFO", f"图片「{slot}」还没有导出文件")


# ---------- 平台间重复 ----------

def main_text(post: dict) -> str:
    for key in ("body", "caption", "note.body"):
        val = get_path(post, key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def title_like(post: dict) -> set[str]:
    out: set[str] = set()
    for key in ("titles", "chosen_title", "cover_text", "chosen_cover_text", "note.title"):
        val = get_path(post, key)
        for t in (val if isinstance(val, list) else [val]):
            if isinstance(t, str) and t.strip():
                out.add(re.sub(r"\s", "", t))
    return out


def first_sentence(text: str) -> str:
    for part in SENTENCE_SPLIT.split(text):
        part = re.sub(r"\s", "", part)
        if part:
            return part
    return ""


def copy_ratio(a: str, b: str, min_run: int = 6) -> float:
    """较短一篇里，有多少字落在两篇共有的、连续 min_run 字以上的片段中。"""
    a, b = re.sub(r"\s", "", a), re.sub(r"\s", "", b)
    if not a or not b:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    shared = sum(m.size for m in sm.get_matching_blocks() if m.size >= min_run)
    return shared / min(len(a), len(b))


def check_cross(codes: list[str], posts: dict[str, dict], reports: dict[str, Report], threshold: float) -> None:
    all_codes = list(posts)
    for a in codes:
        for b in all_codes:
            if a == b:
                continue
            pa, pb = posts[a], posts[b]
            name_b = PLATFORMS[b]["name"]
            for t in title_like(pa) & title_like(pb):
                reports[a].add("FAIL", f"标题「{t}」和{name_b}一样，各平台要分别从内容卡重写")
            fa, fb = first_sentence(main_text(pa)), first_sentence(main_text(pb))
            if fa and fa == fb:
                reports[a].add("FAIL", f"正文第一句「{fa}」和{name_b}一样")
            ta, tb = main_text(pa), main_text(pb)
            ratio = copy_ratio(ta, tb)
            shorter = min(len(re.sub(r"\s", "", ta)), len(re.sub(r"\s", "", tb)))
            limit = threshold if shorter >= 100 else max(threshold, 0.8)  # 短文案共用一两句事实描述很正常
            if ratio > limit:
                reports[a].add("FAIL", f"正文和{name_b}重复 {ratio:.0%}（按较短一篇里连续 6 字以上相同的部分计），"
                                       f"超过 {limit:.0%}，属于一文多发")


# ---------- 报告 ----------

def write_report(run: pathlib.Path) -> pathlib.Path:
    lint_dir = run / ".lint"
    lines = ["# 审核报告", "", f"更新时间：{now()}", ""]
    for code, meta in PLATFORMS.items():
        path = lint_dir / f"{code}.json"
        if not path.exists():
            continue
        data = load_json(path)
        lines += [f"## {meta['name']}（检查于 {data['checked_at']}）", ""]
        for level, title in (("fail", "FAIL（必须改）"), ("warn", "WARN（逐条判断）"), ("info", "INFO")):
            items = data["result"].get(level) or []
            lines.append(f"**{title}：{len(items)} 项**")
            lines.append("")
            lines += [f"- {x}" for x in items] or ["- 无"]
            lines.append("")
    out = run / "06_审核报告.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="输出目录，例如 输出/2026-11-23_主题")
    ap.add_argument("--platform", help="只检查这个平台（平台代号）")
    ap.add_argument("--data-dir", help="用户数据目录，默认 ./yiyuan-data")
    ap.add_argument("--workbench", help="工作台目录，默认 ./workbench")
    ap.add_argument("--dup-threshold", type=float, default=0.5, help="平台间正文相似度上限，默认 0.5")
    ap.add_argument("--json", action="store_true", help="同时把结果以 JSON 打印出来")
    args = ap.parse_args()

    run = pathlib.Path(args.run)
    if not run.is_dir():
        sys.exit(f"找不到输出目录：{run}")
    present = existing_platforms(run)
    codes = [check_platform(args.platform)] if args.platform else present
    if args.platform and args.platform not in present:
        sys.exit(f"找不到 {post_path(run, args.platform)}")
    if not codes:
        sys.exit("输出目录里还没有任何平台的 post.json")

    card_path = run / "00_内容卡.json"
    card = load_json(card_path) if card_path.exists() else None
    brand = data_dir(args.data_dir) / "brand.md"
    wb = workbench_dir(args.workbench)
    groups = load_banned(brand)
    posts = {code: load_json(post_path(run, code)) for code in present}
    reports = {code: Report() for code in codes}

    for code in codes:
        post, rep = posts[code], reports[code]
        check_limits(code, post, rep)
        check_banned(code, post, groups, rep)
        check_facts(post, card, rep)
        check_image_fields(post, run, rep)
        check_declarations(code, post, rep)
        check_benchmark_copy(code, post, run, wb, rep)
        check_image_files(code, post, run, rep)
        for item in post.get("needs_human") or []:
            rep.add("INFO", f"needs_human：{item}")
    check_cross(codes, posts, reports, args.dup_threshold)

    total_fail = 0
    summary = {}
    for code in codes:
        result = reports[code].as_dict()
        save_json(run / ".lint" / f"{code}.json", {"checked_at": now(), "result": result})
        summary[code] = result
        total_fail += len(result["fail"])
        print(f"[{PLATFORMS[code]['name']}] FAIL {len(result['fail'])} · WARN {len(result['warn'])} · INFO {len(result['info'])}")
        for level in ("fail", "warn"):
            for msg in result[level]:
                print(f"  {level.upper()}: {msg}")
    report = write_report(run)
    print(f"审核报告：{report}")
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
