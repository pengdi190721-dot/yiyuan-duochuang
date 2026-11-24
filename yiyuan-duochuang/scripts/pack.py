#!/usr/bin/env python3
"""第 ⑨ 步：生成 发布总览.html（主交付物）、各平台发布文案和 07_交付清单.md。

用法：
  python3 pack.py --run "输出/2026-11-23_主题"
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import FONT_WHITELIST, PLATFORMS, data_dir, existing_platforms, load_json, now, platform_dir, post_path, selected_images  # noqa: E402
from render_publish import build as build_publish_html  # noqa: E402

DECLARATIONS = {
    "douyin": "自主声明勾选\"内容由 AI 生成\"；推广内容加选\"营销推广信息\"",
    "shipinhao": "添加声明勾选 AI 创作声明",
    "gongzhonghao": "勾选平台的 AI 生成内容声明；确认配图下方已注明\"AI 生成\"",
    "xiaohongshu": "确认正文已注明\"部分图片由 AI 辅助生成\"；达人合作走蒲公英报备",
    "ctrip": "按内容中心发布页选项勾选；没有对应选项时在正文末尾注明",
}


def pick(post: dict, chosen: str, options: str) -> str:
    val = post.get(chosen)
    if isinstance(val, str) and val.strip():
        return val
    opts = post.get(options)
    if isinstance(opts, list) and opts:
        return f"{opts[0]}（交互点 A 还没选，暂用第一个）"
    return opts if isinstance(opts, str) else ""


def tags_line(items) -> str:
    items = items or []
    return " ".join(t if t.startswith("#") else f"#{t}" for t in items if isinstance(t, str) and t)


def publish_text(code: str, post: dict) -> str:
    images = selected_images(post)
    img_lines = [f"{i:02d}. {img.get('slot', '')}：{img.get('on_image_text', '')}" for i, img in enumerate(images, 1)]
    if code == "xiaohongshu":
        parts = [f"标题：{pick(post, 'chosen_title', 'titles')}", "", post.get("body", ""), "", tags_line(post.get("tags"))]
    elif code in ("douyin", "shipinhao"):
        parts = [f"首图大字：{pick(post, 'chosen_cover_text', 'cover_text')}", "", post.get("caption", ""), "",
                 tags_line(post.get("topics"))]
        if code == "douyin" and post.get("poi"):
            parts += ["", f"定位：{post['poi']}"]
    elif code == "gongzhonghao":
        parts = [f"标题：{pick(post, 'chosen_title', 'titles')}", f"摘要：{post.get('digest', '')}", "",
                 post.get("body", ""), "", post.get("cta", "")]
    else:
        note = post.get("note") or {}
        replies = post.get("review_replies") or {}
        parts = [f"【内容中心笔记】标题：{note.get('title', '')}", "", note.get("body", ""), "",
                 "【亮点】", *[f"- {h}" for h in post.get("highlights") or []], "",
                 "【详情页模块】", *[f"- {m.get('module', '')}：{m.get('text', '')}" for m in post.get("detail_modules") or []], "",
                 "【点评回复模板】", f"- 好评：{replies.get('good', '')}", f"- 中评：{replies.get('neutral', '')}",
                 f"- 差评：{replies.get('bad', '')}"]
    parts += ["", "【图片顺序】", *img_lines, "", f"【发布时要勾选】{DECLARATIONS[code]}"]
    return "\n".join(parts).strip() + "\n"


def collect_placeholders(run: pathlib.Path) -> list[str]:
    found = []
    for path in [run / "00_内容卡.json", *[post_path(run, c) for c in existing_platforms(run)]]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in sorted(set(re.findall(r"【待补[^】]*】", text))):
            found.append(f"{path.relative_to(run)}：{m}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--data-dir", help="用户数据目录，默认 ./yiyuan-data")
    args = ap.parse_args()
    run = pathlib.Path(args.run)
    codes = existing_platforms(run)
    if not codes:
        sys.exit("输出目录里还没有任何平台的 post.json")
    card = load_json(run / "00_内容卡.json") if (run / "00_内容卡.json").exists() else {}

    needs_human, missing_imgs = [], []
    for code in codes:
        post = load_json(post_path(run, code))
        name = PLATFORMS[code]["name"]
        fname = "正文.md" if code == "gongzhonghao" else ("内容中心笔记与模板.txt" if code == "ctrip" else "发布文案.txt")
        (platform_dir(run, code) / fname).write_text(publish_text(code, post), encoding="utf-8")
        needs_human += [f"{name}：{x}" for x in post.get("needs_human") or []]
        img_dir = platform_dir(run, code) / "图片"
        have = {p.stem.split("_", 1)[-1] for p in img_dir.glob("*.jpg")} if img_dir.is_dir() else set()
        for img in selected_images(post):
            slot = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(img.get("slot", ""))).strip("_")
            if slot not in have:
                missing_imgs.append(f"{name}：{img.get('slot')}")

    fonts_used, below = set(), []
    csv_path = run / "images.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if row.get("status") != "ok":
                    continue
                for f in (row.get("font") or "").split(";"):
                    if f:
                        fonts_used.add(f)
                if row.get("note") == "below_target":
                    below.append(row.get("file", ""))
    lic = {f["file"]: f["name"] for f in FONT_WHITELIST}
    lic.update({f["style"]: f["name"] for f in FONT_WHITELIST})

    lines = ["# 交付清单", "", f"生成时间：{now()}", ""]
    lines += ["## 1. 待补信息", ""] + ([f"- {x}" for x in collect_placeholders(run)] or ["- 无"]) + [""]
    lines += ["## 2. 需补拍的原图", ""] + ([f"- {x}" for x in card.get("missing_photos") or []] or ["- 无"]) + [""]
    lines += ["## 3. 标记\"需人工\"的稿件和图片", ""] + ([f"- {x}" for x in needs_human] or ["- 无"]) + [""]
    if missing_imgs or below:
        lines += ["## 3b. 图片提醒", ""] + [f"- 未生成：{x}" for x in missing_imgs] + [f"- 分辨率低于平台建议：{x}" for x in below] + [""]
    lines += ["## 4. 各平台发布时要勾选的声明", ""] + [f"- {PLATFORMS[c]['name']}：{DECLARATIONS[c]}" for c in codes] + [""]
    lines += ["## 5. 本次用到的字体及授权", ""]
    lines += [f"- {lic.get(f, f)}：{'SIL OFL 1.1，可免费商用' if f in lic else '用户登记的授权字体，见 brand.md'}" for f in sorted(fonts_used)] or ["- 无"]
    (run / "07_交付清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    record = run / "交互记录.md"
    if not record.exists():
        record.write_text("# 交互记录\n\n", encoding="utf-8")
    overview = build_publish_html(run, data_dir(args.data_dir))
    print(json.dumps({"platforms": codes, "needs_human": len(needs_human), "missing_images": missing_imgs,
                      "below_target": below, "checklist": str(run / "07_交付清单.md"),
                      "publish_overview": str(overview)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
