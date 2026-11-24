#!/usr/bin/env python3
"""生成 发布总览.html：一个素材、五种讲法，每个平台一张卡片，带"复制全文 / 只复制标题 / 只复制正文"按钮和配图。

用法：
  python3 render_publish.py --run "输出/2026-11-23_主题"
pack.py 会自动调用它；单独运行也可以。页面写在输出目录下：发布总览.html。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PLATFORMS, brand_name, char_count, data_dir, existing_platforms, load_json, now,
    platform_dir, post_path, selected_images,
)
from _html import esc, hero, json_for_script, page, url  # noqa: E402

ORDER = ["xiaohongshu", "douyin", "shipinhao", "gongzhonghao", "ctrip"]
ROLE = {"xiaohongshu": "搜索种草", "douyin": "引爆曝光", "shipinhao": "熟人信任",
        "gongzhonghao": "深度沉淀", "ctrip": "决策转化"}
DECLARATIONS = {
    "douyin": "自主声明勾选\"内容由 AI 生成\"；推广内容加选\"营销推广信息\"。",
    "shipinhao": "添加声明里勾选 AI 创作声明；带货内容的 AI 海报必须标注。",
    "gongzhonghao": "勾选平台的 AI 生成内容声明；确认配图下方已注明\"AI 生成\"。",
    "xiaohongshu": "用专业号发布；确认正文已注明\"部分图片由 AI 辅助生成\"；达人合作走蒲公英报备。",
    "ctrip": "价格、日期、包含项发布前再和商家后台核对一遍；按内容中心发布页选项勾选声明。",
}

EXTRA_CSS = """
.pcard{margin:18px 0}
.ph{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ph h3{margin:0;font-size:16px}
.ph .meta{margin-left:auto;color:var(--muted);font-size:12px}
.title{font-size:16px;font-weight:700;margin:2px 0}
.body{white-space:pre-wrap;word-break:break-word;color:var(--ink)}
.body.article p{margin:0 0 12px;text-indent:2em}
.tags{color:var(--red);word-break:break-word}
.list{margin:4px 0;padding-left:18px}
.imgs{display:flex;gap:8px;overflow-x:auto;padding:4px 0 2px}
.imgs a{flex:0 0 auto;position:relative}
.imgs img{height:120px;border-radius:6px;border:1px solid var(--line);display:block}
.imgs span{position:absolute;left:4px;top:4px;background:rgba(0,0,0,.6);color:#fff;font-size:11px;border-radius:3px;padding:0 5px}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.btn{border:1px solid var(--line);background:#fff;border-radius:6px;padding:6px 14px;font-size:13px;cursor:pointer;color:var(--ink);font-family:inherit}
.btn.primary{background:var(--dark);border-color:var(--dark);color:#fff}
.btn:hover{border-color:var(--ink)}
.remind{margin-top:14px;border-left:3px solid var(--red);background:#fbf7f7;padding:8px 12px;font-size:12.5px;color:var(--ink2);border-radius:0 6px 6px 0}
.remind b{color:var(--red);font-weight:600}
details{margin-top:6px}
summary{cursor:pointer;color:var(--ink2);font-size:13px}
"""


def first(post: dict, chosen: str, options: str) -> str:
    val = post.get(chosen)
    if isinstance(val, str) and val.strip():
        return val.strip()
    opts = post.get(options)
    if isinstance(opts, list) and opts and isinstance(opts[0], str):
        return opts[0].strip()
    return opts.strip() if isinstance(opts, str) else ""


def hashtags(items) -> str:
    return " ".join(t if t.startswith("#") else f"#{t}" for t in (items or []) if isinstance(t, str) and t.strip())


def placeholders(post: dict) -> list[str]:
    text = str(post)
    return sorted({m.strip("：: ") or "未写明" for m in re.findall(r"【待补([^】]*)】", text)})


def platform_view(code: str, post: dict) -> dict:
    """把 post.json 变成卡片里要显示的字段，以及三个复制按钮各复制什么。"""
    fields: list[tuple[str, str, str]] = []  # (标签, 内容, 样式类)
    if code == "xiaohongshu":
        title, body, tail = first(post, "chosen_title", "titles"), post.get("body", ""), hashtags(post.get("tags"))
        fields = [("标题", title, "title"), ("正文", body, "body"), ("话题标签", tail, "tags")]
        full = "\n\n".join(x for x in (title, body, tail) if x)
    elif code in ("douyin", "shipinhao"):
        title, body = first(post, "chosen_cover_text", "cover_text"), post.get("caption", "")
        tail = hashtags(post.get("topics"))
        if code == "douyin" and post.get("poi"):
            tail_view, tail_label = f"{tail}　📍{post['poi']}", "话题 / 定位"
        elif code == "shipinhao" and post.get("follow_up"):
            tail_view, tail_label = f"{tail}　→ {post['follow_up']}", "话题 / 承接"
        else:
            tail_view, tail_label = tail, "话题"
        fields = [("首图大字" if code == "douyin" else "首图文字", title, "title"), ("正文", body, "body"),
                  (tail_label, tail_view, "tags")]
        full = "\n\n".join(x for x in (body, tail) if x)
    elif code == "gongzhonghao":
        title, body, digest, cta = first(post, "chosen_title", "titles"), post.get("body", ""), post.get("digest", ""), post.get("cta", "")
        fields = [("标题", title, "title"), ("正文", body, "article"), ("文末转化", cta, "body"), ("摘要", digest, "body")]
        body = "\n\n".join(x for x in (body, cta) if x)
        full = "\n\n".join(x for x in (title, body) if x)
    else:
        note = post.get("note") or {}
        title, body = note.get("title", ""), note.get("body", "")
        hl = post.get("highlights") or []
        fields = [("标题", title, "title"), ("正文", body, "body"), ("详情页亮点", "\n".join(hl), "list")]
        modules = post.get("detail_modules") or []
        if any(m.get("text") for m in modules if isinstance(m, dict)):
            fields.append(("详情页模块", "\n".join(f"【{m.get('module', '')}】{m.get('text', '')}" for m in modules if isinstance(m, dict)), "body"))
        replies = post.get("review_replies") or {}
        if any(replies.values()):
            fields.append(("点评回复模板", "\n".join(f"{k}：{v}" for k, v in (("好评", replies.get("good")), ("中评", replies.get("neutral")), ("差评", replies.get("bad"))) if v), "body"))
        full = "\n\n".join(x for x in (title, body) if x)
    return {"fields": fields, "title": title, "body": body, "full": full}


def render_field(label: str, value: str, kind: str) -> str:
    if not value:
        return ""
    if kind == "article":
        paras = "".join(f"<p>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n|\n", value) if p.strip())
        inner = f'<div class="body article">{paras}</div>'
    elif kind == "list":
        inner = '<ul class="list">' + "".join(f"<li>{esc(x)}</li>" for x in value.split("\n") if x.strip()) + "</ul>"
    else:
        inner = f'<div class="{kind}">{esc(value)}</div>'
    return f'<div class="label">{esc(label)}</div>{inner}'


def render_images(run: pathlib.Path, code: str) -> str:
    img_dir = platform_dir(run, code) / "图片"
    files = sorted(p for p in img_dir.glob("*.jpg")) if img_dir.is_dir() else []
    if not files:
        return ""
    items = "".join(
        f'<a href="{url(str(p.relative_to(run)))}" target="_blank"><img loading="lazy" src="{url(str(p.relative_to(run)))}" alt="{esc(p.stem)}"><span>{i:02d}</span></a>'
        for i, p in enumerate(files, 1))
    return f'<div class="label">配图（按发布顺序，点开看大图）</div><div class="imgs">{items}</div>'


def build(run: pathlib.Path, ddir: pathlib.Path) -> pathlib.Path:
    codes = [c for c in ORDER if c in existing_platforms(run)]
    if not codes:
        sys.exit("输出目录里还没有任何平台的 post.json")
    card = load_json(run / "00_内容卡.json") if (run / "00_内容卡.json").exists() else {}
    topic = card.get("topic") or run.name.split("_", 1)[-1]
    brand = brand_name(ddir)
    copy: dict[str, str] = {}
    chips, cards = [], []
    for n, code in enumerate(codes, 1):
        post = load_json(post_path(run, code))
        view = platform_view(code, post)
        name = PLATFORMS[code]["name"]
        sid = f"p{n}"
        chips.append(f'<a class="chip" href="#{sid}">{n:02d} {esc(name)}</a>')
        copy[f"{code}-full"], copy[f"{code}-title"], copy[f"{code}-body"] = view["full"], view["title"], view["body"]
        meta = [f"{char_count(view['body'])} 字", f"{len(selected_images(post))} 张图"]
        if code == "gongzhonghao" and post.get("template") and "/" not in post["template"]:
            meta.append(post["template"])
        remind = [DECLARATIONS[code]]
        remind += [f"需人工：{x}" for x in post.get("needs_human") or []]
        remind += [f"待补：{x}" for x in placeholders(post)]
        fields_html = "".join(render_field(*f) for f in view["fields"])
        cards.append(
            f'<article class="card pcard" id="{sid}"><div class="ph"><span class="num">{n:02d}</span>'
            f'<h3>{esc(name)}</h3><span class="tag">{esc(ROLE[code])}</span>'
            f'<span class="meta">{esc(" · ".join(meta))}</span></div>{fields_html}{render_images(run, code)}'
            f'<div class="btns"><button class="btn primary" data-copy="{code}-full">复制全文</button>'
            f'<button class="btn" data-copy="{code}-title">只复制标题</button>'
            f'<button class="btn" data-copy="{code}-body">只复制正文</button></div>'
            f'<div class="remind"><b>发布提醒：</b>{"<br>".join(esc(x) for x in remind)}</div></article>')
    title = f"{topic} · {brand}" if brand else topic
    body = (hero("PUBLISH COPY", esc(title), "一个素材，五种讲法。点「复制全文」直接粘贴到对应平台；配图按顺序上传。")
            + f'<div class="nav"><div class="wrap"><div class="chips">{"".join(chips)}</div></div></div>'
            + f'<main class="wrap">{"".join(cards)}'
            + '<div class="tip">想让下次更像你喜欢的样子？可以随时把喜欢的<b>对标图片</b>或<b>文案</b>发给我，'
              '并说明用在哪个平台；之后出稿会按它调整，同时保留各平台自己的调性。</div></main>'
            + f'<div class="foot">生成于 {esc(now())} · 数据源 {esc(run.as_posix())}/各平台 post.json</div>')
    out = run / "发布总览.html"
    out.write_text(page(f"发布总览 · {title}", body, EXTRA_CSS, f"window.COPY={json_for_script(copy)};"), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--data-dir", help="用户数据目录，默认 ./yiyuan-data")
    args = ap.parse_args()
    out = build(pathlib.Path(args.run), data_dir(args.data_dir))
    print(f"发布总览：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
