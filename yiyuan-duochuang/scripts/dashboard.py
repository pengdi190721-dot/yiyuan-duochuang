#!/usr/bin/env python3
"""生成 内容数据中台.html：总览、账号矩阵、平台表现、作品明细、经营基本面、诊断结论、本次发布建议（含拍摄清单）。

用法：
  python3 dashboard.py                 # 读 workbench/数据/，写 workbench/内容数据中台.html
  python3 dashboard.py --workbench 路径 --data-dir 路径

数字全部由脚本从 workbench/数据/ 计算；模型只写三个 JSON（都可以没有，没有就不显示对应部分）：
  workbench/数据/经营基本面.json   模板 templates/business_kpis.json
  workbench/数据/诊断结论.json     模板 templates/diagnosis.json
  workbench/数据/发布建议.json     模板 templates/publish_advice.json
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import shutil
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import PLATFORMS, brand_name, data_dir, now, workbench_dir  # noqa: E402
from _html import esc, hero, page, platform_tag, section  # noqa: E402

EXTRA_CSS = """
.grid{display:grid;gap:12px}
.g5{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.kpi .k{font-size:12px;color:var(--muted)}
.kpi .v{font-size:26px;font-weight:700;margin:2px 0;font-variant-numeric:tabular-nums}
.kpi .s{font-size:11.5px;color:var(--muted)}
.kpi{border-top:3px solid var(--red)}
.acc .name{font-weight:700;font-size:14px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.acc .stats{display:flex;gap:14px;margin:8px 0 4px;flex-wrap:wrap}
.acc .stats b{display:block;font-size:18px;font-variant-numeric:tabular-nums;white-space:nowrap}
.acc .stats span{font-size:11px;color:var(--muted)}
.bar{height:5px;background:#efedea;border-radius:3px;overflow:hidden;margin-top:8px}
.bar i{display:block;height:100%;background:var(--red)}
.bar i.grey{background:#c9c6c1}
.hrow{margin:10px 0}
.hrow .t{display:flex;justify-content:space-between;font-size:12.5px}
.hist{display:flex;align-items:flex-end;gap:10px;height:170px;padding-top:18px}
.hist .col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.hist .col i{display:block;width:100%;background:var(--red);border-radius:4px 4px 0 0;min-height:2px}
.hist .col b{font-size:12px;margin-bottom:4px}
.hist .col span{font-size:11px;color:var(--muted);margin-top:4px}
.ctrl{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.ctrl input{flex:1;min-width:200px;border:1px solid var(--line);border-radius:6px;padding:7px 10px;font:inherit;background:#fff}
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:500;cursor:pointer;white-space:nowrap;user-select:none}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}
td.t{min-width:260px}
td a{color:var(--muted)}
.diag .lv{margin-bottom:6px}
.diag h4{margin:0 0 6px;font-size:14px}
.diag p{margin:0;color:var(--ink2);font-size:13px}
.diag .ev{margin-top:8px;font-size:11.5px;color:var(--muted)}
.advice-head{font-size:15px;font-weight:600;margin:0 0 10px}
.shots td{font-size:13px}
.pri{display:inline-block;padding:0 6px;border-radius:4px;font-size:11px;background:var(--red-soft);color:var(--red)}
.pri.mid{background:#f1f0ee;color:var(--ink2)}
"""

TABLE_JS = """
(function(){const tb=document.querySelector('#posts tbody');if(!tb)return;const rows=[...tb.rows];
let plat='全部';const q=document.getElementById('q');
function apply(){const s=(q.value||'').trim().toLowerCase();rows.forEach(r=>{const okP=plat==='全部'||r.dataset.p===plat;
const okS=!s||r.textContent.toLowerCase().includes(s);r.style.display=okP&&okS?'':'none'})}
q.addEventListener('input',apply);
document.querySelectorAll('[data-plat]').forEach(c=>c.addEventListener('click',()=>{plat=c.dataset.plat;
document.querySelectorAll('[data-plat]').forEach(x=>x.classList.toggle('on',x===c));apply()}));
document.querySelectorAll('#posts th[data-k]').forEach((th,i)=>{let asc=false;th.addEventListener('click',()=>{asc=!asc;
const k=+th.dataset.k;rows.sort((a,b)=>{const x=a.cells[k].dataset.v??a.cells[k].textContent,y=b.cells[k].dataset.v??b.cells[k].textContent;
const nx=parseFloat(x),ny=parseFloat(y);const c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y),'zh');return asc?c:-c});
rows.forEach(r=>tb.appendChild(r))})})})();
"""


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def num(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.1f}"
    if v >= 10000:
        return f"{v / 10000:.1f}万"
    return str(v)


def load_opt(path: pathlib.Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def kpis(posts: list[dict], accounts: list[dict], prev_posts: list[dict], prev_date: str | None) -> str:
    likes = [num(p["点赞"]) for p in posts if num(p["点赞"]) is not None]
    total, n = sum(likes), len(posts)
    avg = total / len(likes) if likes else 0.0
    top = max(likes) if likes else None
    prev_likes = [num(p["点赞"]) for p in prev_posts if num(p["点赞"]) is not None]
    delta_total = f"较 {prev_date[5:]} {'+' if total - sum(prev_likes) >= 0 else ''}{total - sum(prev_likes)}" if prev_posts and prev_date else "首次采集，暂无对比"
    delta_n = f"较 {prev_date[5:]} {'+' if n - len(prev_posts) >= 0 else ''}{n - len(prev_posts)} 条" if prev_posts and prev_date else ""
    top_title = next((p["标题"] for p in posts if num(p["点赞"]) == top), "") if top is not None else ""
    own_acc = [a for a in accounts if a.get("角色") != "竞品"]
    tiles = [("作品总数", str(n), delta_n or "自家账号公开作品"), ("总点赞", fmt(total), delta_total),
             ("条均点赞", f"{avg:.1f}", f"中位数 {statistics.median(likes):.0f}" if likes else ""),
             ("单条最高", fmt(top), top_title[:16]), ("账号数", str(len(own_acc) or len({p['账号'] for p in posts})), "自家账号")]
    return '<div class="grid g5">' + "".join(
        f'<div class="card kpi"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><div class="s">{esc(s)}</div></div>'
        for k, v, s in tiles) + "</div>"


def account_matrix(posts: list[dict], accounts: list[dict]) -> str:
    stats: dict[tuple, list[int]] = {}
    for p in posts:
        stats.setdefault((p["平台"], p["账号"]), []).append(num(p["点赞"]) or 0)
    acc_by = {(a["平台"], a["账号"]): a for a in accounts}
    keys = [(a["平台"], a["账号"]) for a in accounts] + [k for k in stats if k not in acc_by]
    keys.sort(key=lambda k: acc_by.get(k, {}).get("角色") == "竞品")  # 自家在前，竞品在后
    avgs = {k: (sum(v) / len(v)) for k, v in stats.items() if v}
    best = max(avgs.values()) if avgs else 1
    cards = []
    for k in keys:
        a = acc_by.get(k, {})
        vals = stats.get(k, [])
        avg = avgs.get(k)
        role = a.get("角色", "自家")
        role_tag = '<span class="tag red">竞品</span>' if role == "竞品" else ""
        verified = f'<span class="tag">{esc(a.get("认证"))}</span>' if a.get("认证") else ""
        width = int(100 * (avg or 0) / best) if best else 0
        cards.append(
            f'<div class="card acc"><div class="name">{esc(k[1])} {platform_tag(k[0])} {role_tag}{verified}</div>'
            f'<div class="stats"><div><b>{esc(fmt(num(a.get("粉丝"))))}</b><span>粉丝</span></div>'
            f'<div><b>{esc(fmt(num(a.get("获赞与收藏"))))}</b><span>获赞与收藏</span></div>'
            f'<div><b>{esc(f"{avg:.1f}" if avg is not None else "—")}</b><span>条均点赞</span></div></div>'
            f'<div class="muted" style="font-size:12px">采集到 {len(vals)} 条作品{f" · 最高 {max(vals)} 赞" if vals else ""}</div>'
            f'<div class="bar"><i style="width:{width}%"></i></div></div>')
    return '<div class="grid g4">' + "".join(cards) + "</div>" if cards else '<div class="card muted">还没有账号数据。</div>'


def platform_perf(posts: list[dict]) -> str:
    groups: dict[str, list[int]] = {}
    per_platform_accounts: dict[str, set] = {}
    for p in posts:
        per_platform_accounts.setdefault(p["平台"], set()).add(p["账号"])
    for p in posts:
        label = p["平台"] if len(per_platform_accounts[p["平台"]]) == 1 else f'{p["平台"]}·{p["账号"]}'
        groups.setdefault(label, []).append(num(p["点赞"]) or 0)
    rows = sorted(((k, sum(v) / len(v), len(v)) for k, v in groups.items() if v), key=lambda x: -x[1])
    overall = (sum(num(p["点赞"]) or 0 for p in posts) / len(posts)) if posts else 0
    best = rows[0][1] if rows else 1
    bars = "".join(
        f'<div class="hrow"><div class="t"><span>{esc(k)} <span class="muted">· {n} 条</span></span><b>{a:.1f}</b></div>'
        f'<div class="bar"><i class="{"" if a >= overall else "grey"}" style="width:{int(100 * a / best) if best else 0}%"></i></div></div>'
        for k, a, n in rows)
    likes = [num(p["点赞"]) for p in posts if num(p["点赞"]) is not None]
    big = likes and statistics.median(likes) > 100
    bins = ([(0, 50), (51, 100), (101, 500), (501, 1000), (1001, None)] if big else [(0, 5), (6, 10), (11, 20), (21, 50), (51, None)])
    counts = [sum(1 for x in likes if x >= lo and (hi is None or x <= hi)) for lo, hi in bins]
    mx = max(counts) if counts and max(counts) else 1
    cols = "".join(
        f'<div class="col"><b>{c}</b><i style="height:{int(100 * c / mx)}%"></i><span>{lo}{"+" if hi is None else f"–{hi}"}</span></div>'
        for (lo, hi), c in zip(bins, counts))
    low = counts[0] if counts else 0
    caption = (f"{len(likes)} 条作品中 {low} 条点赞在 {bins[0][0]}–{bins[0][1]}（{low * 100 // len(likes) if likes else 0}%），"
               f"条均 {overall:.1f}。") if likes else "暂无点赞数据。"
    return (f'<div class="grid g2"><div class="card"><b>各平台平均点赞</b><div class="muted" style="font-size:12px">红色为高于全部作品平均（{overall:.1f}）</div>{bars or "<p class=muted>暂无</p>"}</div>'
            f'<div class="card"><b>点赞分布（{len(likes)} 条作品）</b><div class="hist">{cols}</div>'
            f'<div class="muted" style="font-size:12px;margin-top:8px">{esc(caption)}</div></div></div>')


def post_table(posts: list[dict]) -> str:
    plats = sorted({p["平台"] for p in posts})
    chips = '<span class="chip on" data-plat="全部">全部</span>' + "".join(f'<span class="chip" data-plat="{esc(x)}">{esc(x)}</span>' for x in plats)
    head = "".join(f'<th data-k="{i}">{h}</th>' for i, h in enumerate(["点赞 ▾", "收藏", "评论", "标题", "账号", "平台", "发布日期", "链接"]))
    body = []
    posts = sorted(posts, key=lambda p: p.get("角色") == "竞品")  # 自家在前，竞品在后（各自已按点赞排序）
    for p in posts:
        link = f'<a href="{esc(p["链接"])}" target="_blank" rel="noopener">打开</a>' if p.get("链接") else "—"
        body.append(
            f'<tr data-p="{esc(p["平台"])}"><td class="n" data-v="{num(p["点赞"]) if num(p["点赞"]) is not None else -1}">{esc(fmt(num(p["点赞"])))}</td>'
            f'<td class="n" data-v="{num(p["收藏"]) if num(p["收藏"]) is not None else -1}">{esc(fmt(num(p["收藏"])))}</td>'
            f'<td class="n" data-v="{num(p["评论"]) if num(p["评论"]) is not None else -1}">{esc(fmt(num(p["评论"])))}</td>'
            f'<td class="t">{esc(p["标题"])}{" <span class=tag>竞品</span>" if p.get("角色") == "竞品" else ""}</td>'
            f'<td>{esc(p["账号"])}</td><td>{platform_tag(p["平台"])}</td><td class="n">{esc(p["发布日期"] or "—")}</td><td>{link}</td></tr>')
    return (f'<div class="card"><div class="ctrl"><input id="q" placeholder="搜索标题、账号，例如：早餐、亲子、夜景">{chips}</div>'
            f'<div class="tbl-wrap"><table id="posts"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div></div>')


def _items(data):
    return data.get("items") if isinstance(data, dict) else data


def business(items) -> str:
    items = _items(items)
    if not isinstance(items, list) or not items:
        return ""
    return '<div class="grid g5">' + "".join(
        f'<div class="card kpi"><div class="k">{esc(i.get("label"))}</div><div class="v">{esc(i.get("value"))}</div><div class="s">{esc(i.get("note", ""))}</div></div>'
        for i in items if isinstance(i, dict)) + "</div>"


def diagnosis(items) -> str:
    items = _items(items)
    if not isinstance(items, list) or not items:
        return ""
    cards = []
    for i, d in enumerate(items, 1):
        if not isinstance(d, dict):
            continue
        ev = f'<div class="ev">依据：{esc(d["evidence"])}</div>' if d.get("evidence") else ""
        cards.append(
            f'<div class="card diag"><div class="lv"><span class="tag red">{esc(d.get("level", "结论"))}</span></div>'
            f'<h4>{i:02d} {esc(d.get("title"))}</h4><p>{esc(d.get("body"))}</p>{ev}</div>')
    return '<div class="grid g3">' + "".join(cards) + "</div>"


def advice(data) -> str:
    if not isinstance(data, dict):
        return ""
    parts = []
    if data.get("headline"):
        parts.append(f'<p class="advice-head">{esc(data["headline"])}</p>')
    topics = data.get("topics") or []
    if topics:
        cards = []
        for t in topics:
            if not isinstance(t, dict):
                continue
            lead = PLATFORMS.get(t.get("lead_platform", ""), {}).get("name", t.get("lead_platform", ""))
            others = f'<div class="ev">其他平台：{esc(t["others"])}</div>' if t.get("others") else ""
            cards.append(f'<div class="card diag"><div class="lv"><span class="tag red">主打 {esc(lead)}</span></div>'
                         f'<h4>{esc(t.get("topic"))}</h4><p>{esc(t.get("why"))}</p>{others}</div>')
        parts.append('<div class="grid g3">' + "".join(cards) + "</div>")
    shots = data.get("shots") or []
    if shots:
        rows = "".join(
            f'<tr><td><span class="pri {"" if s.get("priority") == "高" else "mid"}">{esc(s.get("priority", "中"))}</span></td>'
            f'<td><b>{esc(s.get("scene"))}</b></td><td>{esc(s.get("how"))}</td><td>{esc(s.get("use"))}</td>'
            f'<td>{esc(s.get("expected"))}</td><td class="muted">{esc(s.get("evidence"))}</td></tr>'
            for s in shots if isinstance(s, dict))
        parts.append('<div class="card" style="margin-top:12px"><b>拍摄清单（交给摄影师）</b><div class="tbl-wrap shots"><table>'
                     '<thead><tr><th>优先级</th><th>拍什么</th><th>怎么拍</th><th>用在哪</th><th>预期效果</th><th>依据</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table></div></div>')
    extra = []
    if data.get("avoid"):
        extra.append("<b>这次不建议：</b>" + "；".join(esc(x) for x in data["avoid"]))
    if data.get("data_gaps"):
        extra.append("<b>数据缺口：</b>" + "；".join(esc(x) for x in data["data_gaps"]))
    if data.get("based_on"):
        extra.append("<b>依据范围：</b>" + esc(data["based_on"]))
    if extra:
        parts.append('<div class="tip" style="margin-top:12px">' + "<br>".join(extra) + "</div>")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbench")
    ap.add_argument("--data-dir")
    args = ap.parse_args()
    wb = workbench_dir(args.workbench)
    d = wb / "数据"
    meta = load_opt(d / "meta.json") or {}
    all_posts = read_csv(d / "作品明细.csv")
    if not all_posts and not (d / "账号.csv").exists():
        sys.exit("workbench/数据/ 里没有数据，先运行 collect_data.py")
    own = [p for p in all_posts if p.get("角色") != "竞品"]
    accounts = read_csv(d / "账号.csv")
    prev_date = meta.get("previous_collected_at")
    prev = [p for p in read_csv(d / "历史" / prev_date / "作品明细.csv") if p.get("角色") != "竞品"] if prev_date else []
    brand = brand_name(data_dir(args.data_dir))
    plats = "/".join(sorted({p["平台"] for p in own})) or "—"
    sub = f"采集日期 {meta.get('collected_at', '—')} · 作品 {len(own)} 条 · {len({(p['平台'], p['账号']) for p in own})} 个账号 · 数据源 {plats}"
    title = f'内容数据中台 · <em>{esc(brand)}</em>' if brand else "内容数据中台"
    secs = [section("01", "总览", kpis(own, accounts, prev, prev_date), "只统计自家账号；对比为上一次采集"),
            section("02", "账号矩阵", account_matrix(own + [p for p in all_posts if p.get("角色") == "竞品"], accounts), "条均点赞越高，进度条越长"),
            section("03", "平台表现", platform_perf(own), "按平台和账号分组"),
            section("04", "作品明细", post_table(all_posts), "点表头排序，点标签筛选平台")]
    n = 5
    for title_s, html_s, note in (("经营基本面", business(load_opt(d / "经营基本面.json")), "来源见每项说明"),
                                  ("诊断结论", diagnosis(load_opt(d / "诊断结论.json")), "每条都写了依据"),
                                  ("本次发布建议", advice(load_opt(d / "发布建议.json")), "基于以上数据和优秀案例")):
        if html_s:
            secs.append(section(f"{n:02d}", title_s, html_s, note))
            n += 1
    body = (hero("CONTENT DATA PLATFORM", title, sub) + f'<main class="wrap">{"".join(secs)}</main>'
            + f'<div class="foot">一源多创 · 数据中台 ｜ 生成于 {esc(now())} ｜ 数据源 workbench/数据/</div>')
    out = wb / "内容数据中台.html"
    out.write_text(page(f"内容数据中台 · {brand}" if brand else "内容数据中台", body, EXTRA_CSS, TABLE_JS), encoding="utf-8")
    hist = d / "历史" / str(meta.get("collected_at", "unknown"))
    hist.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, hist / "内容数据中台.html")
    print(f"内容数据中台：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
