#!/usr/bin/env python3
"""检查和记录初始化状态。

用法：
  python3 setup_check.py --status               # 每次出稿前检查（默认）
  python3 setup_check.py --init-data            # 首次运行第 1 步：建 yiyuan-data/ 和 workbench/，检查环境
  python3 setup_check.py --test-image           # 首次运行第 2 步：调一次 image2.6，确认接口可用
  python3 setup_check.py --mark rules_refreshed # 记录规则刷新日期（也可 --mark initialized）

所有命令都可以加 --data-dir 指定用户数据目录（默认 ./yiyuan-data）。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import FONT_WHITELIST, PLATFORMS, TEMPLATES, data_dir, load_json, now, save_json, today  # noqa: E402

REFRESH_DAYS = 30


def socai_status() -> dict:
    exe = shutil.which("socai")
    if not exe:
        return {"installed": False}
    try:
        out = subprocess.run([exe, "version", "--no-check", "--json"], capture_output=True, text=True, timeout=30)
        info = json.loads(out.stdout) if out.stdout.strip().startswith("{") else {"raw": out.stdout.strip()[:200]}
    except Exception as err:  # noqa: BLE001
        info = {"error": str(err)[:200]}
    return {"installed": True, "path": exe, "version": info}


def status(ddir: pathlib.Path) -> dict:
    setup = load_json(ddir / "config" / "setup.json") if (ddir / "config" / "setup.json").exists() else {}
    try:
        import PIL
        pillow = PIL.__version__
    except ImportError:
        pillow = None
    cfg_path = ddir / "config" / "image.json"
    cfg = load_json(cfg_path) if cfg_path.exists() else {}
    image_ready = bool(cfg.get("base_url")) and "你的" not in cfg.get("base_url", "") and bool(cfg.get("model"))
    brand = ddir / "brand.md"
    brand_filled = brand.exists() and "【待填" not in brand.read_text(encoding="utf-8")
    fonts = [f["file"] for f in FONT_WHITELIST if (ddir / "fonts" / f["file"]).exists()]
    refreshed = setup.get("rules_refreshed")
    due = True
    if refreshed:
        try:
            due = (datetime.date.today() - datetime.date.fromisoformat(refreshed)).days > REFRESH_DAYS
        except ValueError:
            due = True
    rules_latest = sorted(p.stem for p in (ddir / "rules-latest").glob("*.md")) if (ddir / "rules-latest").is_dir() else []
    wb = pathlib.Path.cwd() / "workbench"
    voice = sorted(p.stem for p in (wb / "账号调性").glob("*.md")) if (wb / "账号调性").is_dir() else []
    meta = load_json(wb / "数据" / "meta.json") if (wb / "数据" / "meta.json").exists() else {}
    collected = meta.get("collected_at")
    img_ext = {".jpg", ".jpeg", ".png", ".webp"}
    style_imgs = [p for p in (wb / "风格库" / "图片").rglob("*") if p.suffix.lower() in img_ext] if (wb / "风格库" / "图片").is_dir() else []
    style_copy = list((wb / "风格库" / "文案").rglob("*.md")) if (wb / "风格库" / "文案").is_dir() else []
    cases = (wb / "优秀案例.md").read_text(encoding="utf-8").count("\n### ") if (wb / "优秀案例.md").exists() else 0

    result = {
        "data_dir": str(ddir),
        "initialized": bool(setup.get("initialized")),
        "python": sys.version.split()[0],
        "pillow": pillow,
        "socai": socai_status(),
        "image_config_ready": image_ready,
        "image_api_key_set": bool(os.environ.get("IMAGE_API_KEY")),
        "image_test": setup.get("image_test"),
        "brand_filled": brand_filled,
        "fonts_present": f"{len(fonts)}/{len(FONT_WHITELIST)}",
        "rules_refreshed": refreshed,
        "rules_refresh_due": due,
        "rules_latest_files": rules_latest,
        "voice_profiles": voice,
        "session_type": "再次使用" if setup.get("initialized") else "首次使用",
        "company_profile": (ddir / "公司资料.md").exists(),
        "data_collected_at": collected,
        "data_is_today": collected == today(),
        "dashboard": str(wb / "内容数据中台.html") if (wb / "内容数据中台.html").exists() else None,
        "style_library": {"对标图": len(style_imgs), "喜欢的文案": len(style_copy)},
        "case_entries": cases,
    }
    todo = []
    if not pillow:
        todo.append("安装 Pillow：python3 -m pip install pillow")
    if not result["socai"]["installed"]:
        todo.append("安装 socai（第 1 步），或跳过数据工作台功能")
    if not image_ready:
        todo.append(f"在 {cfg_path} 填 image2.6 的 base_url 和 model（第 2 步）")
    if not result["image_api_key_set"]:
        todo.append("由用户设置环境变量 IMAGE_API_KEY（第 2 步）")
    if not brand_filled:
        todo.append("请用户发公司简介，按 brand_onboarding.md 生成品牌信息和公司资料（第 3 步）")
    if setup.get("initialized") and collected != today():
        todo.append(f"第 0 步：数据复盘与本次发布建议（数据停在 {collected or '从未采集'}，先问用户要不要更新）")
    if due:
        todo.append("搜索最新平台规则（第 5 步）")
    if len(fonts) < len(FONT_WHITELIST):
        todo.append("下载字体：fetch_fonts.py（第 6 步）")
    result["next_steps"] = todo
    return result


def init_data(ddir: pathlib.Path) -> None:
    for sub in ("config", "fonts", "rules-latest"):
        (ddir / sub).mkdir(parents=True, exist_ok=True)
    if not (ddir / "brand.md").exists():
        shutil.copy(TEMPLATES / "brand.template.md", ddir / "brand.md")
    if not (ddir / "config" / "image.json").exists():
        shutil.copy(TEMPLATES / "image_config.example.json", ddir / "config" / "image.json")
    setup_path = ddir / "config" / "setup.json"
    if not setup_path.exists():
        save_json(setup_path, {"created": today()})
    wb = pathlib.Path.cwd() / "workbench"
    subs = ["账号调性", "对标库", "手动导入", "raw", "数据"]
    subs += [f"风格库/图片/{c}" for c in (*PLATFORMS, "通用")] + [f"风格库/文案/{c}" for c in (*PLATFORMS, "通用")]
    for sub in subs:
        (wb / sub).mkdir(parents=True, exist_ok=True)
    (pathlib.Path.cwd() / "输出").mkdir(exist_ok=True)
    print(f"已准备好：{ddir}、{wb}、{pathlib.Path.cwd() / '输出'}")


def mark(ddir: pathlib.Path, key: str) -> None:
    path = ddir / "config" / "setup.json"
    data = load_json(path) if path.exists() else {}
    data[key] = today()
    save_json(path, data)
    print(f"已记录 {key} = {data[key]}")


def test_image(ddir: pathlib.Path) -> int:
    from gen_image import ApiError, call_api
    cfg = load_json(ddir / "config" / "image.json")
    key = os.environ.get("IMAGE_API_KEY", "")
    if not key:
        print("没有设置环境变量 IMAGE_API_KEY")
        return 1
    sizes = (cfg.get("sizes") or {}).get("1:1") or next(iter((cfg.get("sizes") or {}).values()), [])
    if not sizes:
        print("image.json 的 sizes 为空")
        return 1
    size = sizes[-1]
    try:
        data = call_api(cfg, key, "一张浅米色纯色背景的测试图，画面中不要任何文字。", size, [])
    except ApiError as err:
        print(f"测试失败：{err}")
        return 1
    out = ddir / "config" / "test_image.png"
    out.write_bytes(data)
    dims = None
    try:
        from PIL import Image
        with Image.open(out) as im:
            dims = f"{im.size[0]}x{im.size[1]}"
    except Exception:  # noqa: BLE001
        pass
    path = ddir / "config" / "setup.json"
    setup = load_json(path) if path.exists() else {}
    setup["image_test"] = {"time": now(), "requested_size": size, "returned_size": dims, "ok": True}
    save_json(path, setup)
    print(f"测试成功：请求 {size}，返回 {dims}，测试图在 {out}")
    print("最高清档位按 image.json 里每个比例 sizes 的第一项请求；不支持时 gen_image.py 会自动退一档。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--init-data", action="store_true")
    ap.add_argument("--test-image", action="store_true")
    ap.add_argument("--mark", choices=["initialized", "rules_refreshed"])
    args = ap.parse_args()
    ddir = data_dir(args.data_dir)
    if args.init_data:
        init_data(ddir)
    if args.mark:
        mark(ddir, args.mark)
    if args.test_image:
        return test_image(ddir)
    if args.status or args.init_data or not (args.mark or args.test_image):
        print(json.dumps(status(ddir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
