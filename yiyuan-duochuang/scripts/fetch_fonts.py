#!/usr/bin/env python3
"""下载字体白名单里的开源字体（SIL OFL 1.1）到 yiyuan-data/fonts/。

用法：
  python3 fetch_fonts.py                 # 下载全部 8 款，已存在的跳过
  python3 fetch_fonts.py --only 得意黑     # 只下载一款（字体名、文件名或风格类别都可以）
  python3 fetch_fonts.py --list          # 列出白名单
只下载白名单里的字体；对标图用的商用字体一律不下载。
"""
from __future__ import annotations

import argparse
import io
import pathlib
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import FONT_WHITELIST, data_dir  # noqa: E402


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "yiyuan-duochuang-fetch-fonts"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir")
    ap.add_argument("--only")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    fonts_dir = data_dir(args.data_dir) / "fonts"
    if args.list:
        for f in FONT_WHITELIST:
            print(f"{f['name']}\t{f['file']}\t{f['style']}")
        return 0
    fonts_dir.mkdir(parents=True, exist_ok=True)
    targets = [f for f in FONT_WHITELIST
               if not args.only or args.only in (f["name"], f["file"], f["style"]) or args.only in f["name"]]
    if not targets:
        sys.exit(f"白名单里没有「{args.only}」。用 --list 查看。")
    failed = 0
    for f in targets:
        out = fonts_dir / f["file"]
        if out.exists() and out.stat().st_size > 0:
            print(f"已存在：{f['name']}")
            continue
        try:
            data = download(f["url"])
            if f.get("zip_member"):
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    data = zf.read(f["zip_member"])
            out.write_bytes(data)
            print(f"已下载：{f['name']} → {out}（{len(data) // 1024} KB）")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"下载失败：{f['name']}（{err}）。可手动下载 {f['url']} 并存为 {out}")
    (fonts_dir / "LICENSES.md").write_text(
        "# 字体授权\n\n以下字体均为 SIL Open Font License 1.1（https://openfontlicense.org）：\n\n"
        + "\n".join(f"- {f['name']}：{f['file']}，来源 {f['url']}" for f in FONT_WHITELIST) + "\n",
        encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
