"""发布总览.html 和 内容数据中台.html 共用的样式和小工具。纯静态页面，不依赖任何外部资源，离线可打开。"""
from __future__ import annotations

import html
import json
import urllib.parse

CSS = """
:root{--bg:#f4f3f1;--card:#fff;--ink:#1d1d1f;--ink2:#4a4a4f;--muted:#8c8c91;--line:#e8e6e3;
--red:#c8102e;--red-soft:#fdecee;--dark:#141414;--radius:10px;
--font:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:14px;line-height:1.7}
a{color:inherit}
.hero{background:linear-gradient(120deg,#0f0f10 0%,#1b1214 55%,#4b0b16 100%);color:#fff;padding:36px 16px 30px}
.hero-in,.wrap{max-width:1040px;margin:0 auto}
.wrap{padding:0 16px}
.eyebrow{font-size:11px;letter-spacing:.18em;color:#bdbdbd;display:flex;align-items:center;gap:8px}
.eyebrow:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--red)}
.hero h1{margin:10px 0 6px;font-size:26px;line-height:1.3;font-weight:700}
.hero h1 em{font-style:normal;color:#ff4d5e}
.hero .sub{color:#c9c9c9;font-size:12.5px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 6px}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 12px;font-size:12.5px;color:var(--ink2);text-decoration:none;cursor:pointer;white-space:nowrap}
.chip.on,.chip:hover{border-color:var(--ink);color:var(--ink)}
.nav{position:sticky;top:0;z-index:5;background:rgba(244,243,241,.94);backdrop-filter:blur(6px);border-bottom:1px solid transparent}
.sec{margin:28px 0}
.sec-h{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.num{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:22px;padding:0 6px;border-radius:4px;background:var(--dark);color:#fff;font-size:12px;font-weight:700}
.sec-h h2{margin:0;font-size:16px}
.sec-h .note{margin-left:auto;color:var(--muted);font-size:12px;text-align:right}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.tag{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:4px;background:#f1f0ee;color:var(--ink2);white-space:nowrap}
.tag.red{background:var(--red-soft);color:var(--red)}
.muted{color:var(--muted)}
.label{font-size:12px;color:var(--muted);margin:14px 0 4px}
.foot{color:var(--muted);font-size:12px;text-align:center;padding:26px 16px 40px}
.tip{border:1px dashed #d8d4cf;border-radius:var(--radius);padding:12px 16px;color:var(--ink2);font-size:13px;background:#fbfaf8}
@media (max-width:640px){.hero h1{font-size:21px}.card{padding:14px}}
@media print{.nav,.btns,.tip{display:none}.hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""

COPY_JS = """
async function copyText(t){try{await navigator.clipboard.writeText(t);return true}catch(e){
const a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';
document.body.appendChild(a);a.select();let ok=false;try{ok=document.execCommand('copy')}catch(_){}a.remove();return ok}}
document.addEventListener('click',async e=>{const b=e.target.closest('[data-copy]');if(!b)return;
const t=(window.COPY||{})[b.dataset.copy]||'';const ok=await copyText(t);const old=b.dataset.label||b.textContent;
b.dataset.label=old;b.textContent=ok?'已复制':'复制失败，请手动选中复制';setTimeout(()=>{b.textContent=old},1600)});
"""

PLATFORM_TAG_COLORS = {
    "小红书": ("#fff0f2", "#e0213b"),
    "抖音": ("#f0f0f0", "#111111"),
    "视频号": ("#fff4e8", "#d9730d"),
    "公众号": ("#eaf8ef", "#0a8a43"),
    "携程": ("#eaf2fd", "#1f63c6"),
}


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def url(path: str) -> str:
    return urllib.parse.quote(path.replace("\\", "/"))


def platform_tag(name: str) -> str:
    key = next((k for k in PLATFORM_TAG_COLORS if k in (name or "")), None)
    if not key:
        return f'<span class="tag">{esc(name)}</span>'
    bg, fg = PLATFORM_TAG_COLORS[key]
    return f'<span class="tag" style="background:{bg};color:{fg}">{esc(name)}</span>'


def json_for_script(obj) -> str:
    """嵌进 <script> 的 JSON，防止文字里的 </script> 提前结束脚本。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def page(title: str, body: str, extra_css: str = "", extra_js: str = "") -> str:
    return (
        "<!doctype html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{esc(title)}</title><style>{CSS}{extra_css}</style></head><body>"
        f"{body}<script>{COPY_JS}{extra_js}</script></body></html>\n"
    )


def hero(eyebrow: str, title_html: str, sub: str) -> str:
    return (f'<header class="hero"><div class="hero-in"><div class="eyebrow">{esc(eyebrow)}</div>'
            f'<h1>{title_html}</h1><div class="sub">{esc(sub)}</div></div></header>')


def section(num: str, title: str, inner: str, note: str = "", sid: str = "") -> str:
    sid_attr = f' id="{esc(sid)}"' if sid else ""
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    return (f'<section class="sec"{sid_attr}><div class="sec-h"><span class="num">{esc(num)}</span>'
            f'<h2>{esc(title)}</h2>{note_html}</div>{inner}</section>')
