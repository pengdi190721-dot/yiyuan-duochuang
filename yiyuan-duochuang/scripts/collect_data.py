#!/usr/bin/env python3
"""把 socai 采集结果和手动导出的数据整理成工作台数据表，供 dashboard.py 生成内容数据中台。

用法：
  python3 collect_data.py                    # 读 workbench/raw/ 和 workbench/手动导入/，写 workbench/数据/
  python3 collect_data.py --workbench 路径

socai 结果的保存规则（模型执行 socai 命令时把输出重定向成文件）：
  workbench/raw/<YYYY-MM-DD>_<xhs|dy|weixin>_<自家|竞品|搜索>_<说明>.json
  例如：workbench/raw/2026-11-23_xhs_自家_主号.json
手动导入（视频号、携程等 socai 不支持的平台）：
  workbench/手动导入/*.csv，表头：平台,账号,标题,点赞,收藏,评论,分享,发布日期,链接（可选列：角色、类型）

输出：
  workbench/数据/作品明细.csv   自家和竞品的作品（按链接去重）
  workbench/数据/账号.csv       账号资料
  workbench/数据/选题样本.csv   搜索得到的样本（选题和优秀案例用）
  workbench/数据/meta.json      采集日期、上一次快照日期
  workbench/数据/历史/<日期>/    每次整理的快照，用于和前一天对比
互动数换算：1.2万=12000，3.5w=35000，1.5k=1500，999+=999；页面隐藏的数（如"收藏"二字）记为空，不记 0。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import pathlib
import re
import shutil
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import save_json, workbench_dir  # noqa: E402

SITE_NAMES = {"xhs": "小红书", "dy": "抖音", "weixin": "公众号", "tiktok": "TikTok"}
POST_COLS = ["平台", "账号", "角色", "标题", "点赞", "收藏", "评论", "分享", "发布日期", "链接", "类型", "采集日期", "来源文件"]
ACCOUNT_COLS = ["平台", "账号", "角色", "账号ID", "粉丝", "获赞与收藏", "作品数", "认证", "主页", "采集日期"]
RAW_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})_([a-z]+)_([^_]+)")
LIKE_KEYS = ("likes", "liked_count", "digg_count", "like_count")


def to_num(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().replace(",", "").replace("，", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(万|w|W|千|k|K)?\+?", s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2) or ""
    num *= {"万": 10000, "w": 10000, "W": 10000, "千": 1000, "k": 1000, "K": 1000}.get(unit, 1)
    return int(round(num))


def to_date(value, collected: datetime.date) -> str:
    if isinstance(value, dict):
        value = value.get("date") or value.get("at") or ""
    s = str(value or "").strip()
    if not s:
        return ""
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return f"{collected.year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if re.fullmatch(r"\d{10}", s):
        return datetime.date.fromtimestamp(int(s)).isoformat()
    m = re.search(r"(\d+)\s*天前", s)
    if m:
        return (collected - datetime.timedelta(days=int(m.group(1)))).isoformat()
    if "昨天" in s:
        return (collected - datetime.timedelta(days=1)).isoformat()
    if "前天" in s:
        return (collected - datetime.timedelta(days=2)).isoformat()
    if re.search(r"小时前|分钟前|刚刚|今天", s):
        return collected.isoformat()
    return s[:10]


def first_value(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def post_key(url: str, d: dict) -> str:
    for k in ("note_id", "video_id", "aweme_id"):
        if d.get(k):
            return str(d[k])
    parsed = urllib.parse.urlparse(url or "")
    return (parsed.netloc + parsed.path) or url


def short_title(d: dict) -> str:
    t = first_value(d, "title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    text = first_value(d, "description", "desc", "content") or ""
    line = str(text).strip().splitlines()[0] if str(text).strip() else ""
    return line[:40]


def walk(obj, ctx: dict, posts: dict, accounts: dict) -> None:
    if isinstance(obj, list):
        for item in obj:
            walk(item, ctx, posts, accounts)
        return
    if not isinstance(obj, dict):
        return
    name = first_value(obj, "display_name", "nickname")
    if "followers" in obj and name:
        acc = {
            "平台": ctx["platform"], "账号": name, "角色": ctx["role"],
            "账号ID": first_value(obj, "xhs_id", "handle", "author_id", "unique_id") or "",
            "粉丝": to_num(obj.get("followers")), "获赞与收藏": to_num(first_value(obj, "likes_and_collections", "likes", "total_favorited")),
            "作品数": to_num(first_value(obj, "note_count", "video_count", "aweme_count")),
            "认证": obj.get("verification") or ("已认证" if obj.get("verified") else ""),
            "主页": first_value(obj, "url", "profile_url") or "", "采集日期": ctx["date"],
        }
        accounts[(acc["平台"], acc["账号"])] = acc
        ctx = dict(ctx, author=name)
    link = first_value(obj, "url", "link", "share_url")
    if link and any(k in obj for k in LIKE_KEYS) and "followers" not in obj:
        rec = {
            "平台": ctx["platform"], "账号": first_value(obj, "author", "nickname") or ctx.get("author", ""),
            "角色": ctx["role"], "标题": short_title(obj),
            "点赞": to_num(first_value(obj, *LIKE_KEYS)), "收藏": to_num(first_value(obj, "favorites", "collected_count", "collect_count")),
            "评论": to_num(first_value(obj, "comments_count", "comments", "comment_count")),
            "分享": to_num(first_value(obj, "shares", "share_count")),
            "发布日期": to_date(first_value(obj, "published", "date", "created_at", "publish_time", "time"), ctx["collected"]),
            "链接": link, "类型": obj.get("type") or "", "采集日期": ctx["date"], "来源文件": ctx["file"],
        }
        key = (rec["平台"], post_key(link, obj))
        old = posts.get(key)
        if old:  # 同一作品出现多次：按文件日期顺序处理，后读到的非空值覆盖旧值
            for k, v in rec.items():
                if v not in (None, ""):
                    old[k] = v
        else:
            posts[key] = rec
    for k, v in obj.items():
        if isinstance(v, (dict, list)) and k not in ("top_comments", "comments_list", "replies", "sub_comments", "images", "video"):
            walk(v, ctx, posts, accounts)


def read_manual(path: pathlib.Path, today: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "平台": r.get("平台", ""), "账号": r.get("账号", ""), "角色": r.get("角色") or "自家",
                "标题": r.get("标题", ""), "点赞": to_num(r.get("点赞")), "收藏": to_num(r.get("收藏")),
                "评论": to_num(r.get("评论")), "分享": to_num(r.get("分享")),
                "发布日期": to_date(r.get("发布日期"), datetime.date.today()), "链接": r.get("链接", ""),
                "类型": r.get("类型", ""), "采集日期": today, "来源文件": f"手动导入/{path.name}",
            })
    return rows


def write_csv(path: pathlib.Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbench", help="工作台目录，默认 ./workbench")
    args = ap.parse_args()
    wb = workbench_dir(args.workbench)
    raw_files = sorted((wb / "raw").glob("*.json"), key=lambda f: (f.name[:10], f.name))
    manual_files = sorted((wb / "手动导入").glob("*.csv"))
    if not raw_files and not manual_files:
        sys.exit(f"{wb}/raw/ 和 {wb}/手动导入/ 里都没有数据。先按 socai-workbench.md 采集，或放入手动导出的 CSV。")

    posts: dict = {}
    accounts: dict = {}
    dates: list[str] = []
    skipped = []
    for f in raw_files:
        m = RAW_NAME.match(f.stem)
        if not m:
            skipped.append(f.name)
            continue
        date, site, role = m.groups()
        dates.append(date)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as err:  # noqa: BLE001
            skipped.append(f"{f.name}（{err}）")
            continue
        ctx = {"platform": SITE_NAMES.get(site, site), "role": role, "date": date, "file": f"raw/{f.name}",
               "collected": datetime.date.fromisoformat(date)}
        walk(data, ctx, posts, accounts)

    today = datetime.date.today().isoformat()
    rows = list(posts.values())
    for f in manual_files:
        rows += read_manual(f, today)
    own = [r for r in rows if r["角色"] != "搜索"]
    search = [r for r in rows if r["角色"] == "搜索"]
    own.sort(key=lambda r: (r["点赞"] is None, -(r["点赞"] or 0)))
    search.sort(key=lambda r: (r["点赞"] is None, -(r["点赞"] or 0)))

    out = wb / "数据"
    meta_path = out / "meta.json"
    old_meta = {}
    if meta_path.exists():
        try:
            old_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old_meta = {}
    collected_at = max(dates) if dates else today
    # 同一天重跑时保留原来的"上一次"，不同天时上一次就是旧的采集日期
    prev = old_meta.get("previous_collected_at") if old_meta.get("collected_at") == collected_at else old_meta.get("collected_at")
    write_csv(out / "作品明细.csv", POST_COLS, own)
    write_csv(out / "账号.csv", ACCOUNT_COLS, sorted(accounts.values(), key=lambda a: (a["角色"], a["平台"], a["账号"])))
    write_csv(out / "选题样本.csv", POST_COLS, search)
    snap = out / "历史" / collected_at
    snap.mkdir(parents=True, exist_ok=True)
    for name in ("作品明细.csv", "账号.csv"):
        shutil.copy(out / name, snap / name)
    save_json(meta_path, {"collected_at": collected_at, "imported_at": today,
                          "previous_collected_at": prev,
                          "raw_files": [f.name for f in raw_files], "manual_files": [f.name for f in manual_files],
                          "skipped": skipped})
    print(json.dumps({"采集日期": collected_at, "作品": len(own), "账号": len(accounts), "选题样本": len(search),
                      "跳过的文件": skipped, "输出": str(out)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
