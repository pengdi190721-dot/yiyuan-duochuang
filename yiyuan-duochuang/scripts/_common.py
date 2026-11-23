"""一源多创技能脚本的公共定义：平台表、尺寸表、字体白名单和小工具函数。"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys
from typing import Any, Iterator

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"
REFERENCES = SKILL_DIR / "references"

PLATFORMS: dict[str, dict[str, str]] = {
    "douyin": {"name": "抖音图文", "dir": "01_抖音图文"},
    "shipinhao": {"name": "视频号图文", "dir": "02_视频号图文"},
    "gongzhonghao": {"name": "公众号", "dir": "03_公众号"},
    "xiaohongshu": {"name": "小红书", "dir": "04_小红书"},
    "ctrip": {"name": "携程", "dir": "05_携程"},
}

# 平台导出像素（宽, 高），只缩不放。
TARGET_PX: dict[str, tuple[int, int]] = {
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
    "4:3": (1080, 810),
    "2.35:1": (1800, 766),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

TEXT_MODES = ("直接画字", "底图叠字")

# 字体白名单：全部为 SIL Open Font License 1.1。
GOOGLE_RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl"
FONT_WHITELIST: list[dict[str, str]] = [
    {"name": "思源黑体（Noto Sans SC）", "file": "NotoSansSC.ttf", "style": "无衬线",
     "url": f"{GOOGLE_RAW}/notosanssc/NotoSansSC%5Bwght%5D.ttf"},
    {"name": "思源宋体（Noto Serif SC）", "file": "NotoSerifSC.ttf", "style": "宋体",
     "url": f"{GOOGLE_RAW}/notoserifsc/NotoSerifSC%5Bwght%5D.ttf"},
    {"name": "得意黑", "file": "SmileySans-Oblique.ttf", "style": "斜体粗标题",
     "url": "https://github.com/atelier-anchor/smiley-sans/releases/download/v2.0.1/smiley-sans-v2.0.1.zip",
     "zip_member": "SmileySans-Oblique.ttf"},
    {"name": "霞鹜文楷", "file": "LXGWWenKai-Regular.ttf", "style": "手写楷书",
     "url": "https://github.com/lxgw/LxgwWenKai/releases/latest/download/LXGWWenKai-Regular.ttf"},
    {"name": "站酷快乐体", "file": "ZCOOLKuaiLe-Regular.ttf", "style": "圆润可爱",
     "url": f"{GOOGLE_RAW}/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf"},
    {"name": "站酷庆科黄油体", "file": "ZCOOLQingKeHuangYou-Regular.ttf", "style": "粗壮醒目",
     "url": f"{GOOGLE_RAW}/zcoolqingkehuangyou/ZCOOLQingKeHuangYou-Regular.ttf"},
    {"name": "站酷小薇", "file": "ZCOOLXiaoWei-Regular.ttf", "style": "文艺宋体",
     "url": f"{GOOGLE_RAW}/zcoolxiaowei/ZCOOLXiaoWei-Regular.ttf"},
    {"name": "马善政毛笔", "file": "MaShanZheng-Regular.ttf", "style": "毛笔书法",
     "url": f"{GOOGLE_RAW}/mashanzheng/MaShanZheng-Regular.ttf"},
]
STYLE_TO_FILE = {f["style"]: f["file"] for f in FONT_WHITELIST}
DEFAULT_FONT_FILE = "NotoSansSC.ttf"

# 没下载字体时的系统中文字体兜底。
SYSTEM_CJK_FONTS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

# 会被发布出去的字段；lint.py 只检查这些字段里的文字。
PUBLISH_KEYS = {
    "titles", "chosen_title", "cover_text", "chosen_cover_text", "body", "caption",
    "tags", "topics", "digest", "cta", "highlights", "first_comment", "poi",
    "note", "review_replies", "detail_modules",
}
# PUBLISH_KEYS 下面不属于发布内容的子字段。
SKIP_SUBKEYS = {"module", "image_slot", "item", "backend", "match"}


def today() -> str:
    return datetime.date.today().isoformat()


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: pathlib.Path | str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: pathlib.Path | str, obj: Any) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def char_count(text: str) -> int:
    """字数：去掉空白后的字符数。"""
    return len(re.sub(r"\s", "", text or ""))


def data_dir(arg: str | None) -> pathlib.Path:
    return pathlib.Path(arg) if arg else pathlib.Path.cwd() / "yiyuan-data"


def platform_dir(run: pathlib.Path, code: str) -> pathlib.Path:
    return run / PLATFORMS[code]["dir"]


def post_path(run: pathlib.Path, code: str) -> pathlib.Path:
    return platform_dir(run, code) / "post.json"


def existing_platforms(run: pathlib.Path) -> list[str]:
    return [code for code in PLATFORMS if post_path(run, code).exists()]


def check_platform(code: str) -> str:
    if code not in PLATFORMS:
        sys.exit(f"未知平台代号：{code}。可选：{', '.join(PLATFORMS)}")
    return code


def ratio_value(ratio: str) -> float:
    """"3:4" -> 0.75（宽 ÷ 高）。"""
    w, h = ratio.replace("：", ":").split(":")
    return float(w) / float(h)


def get_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _strings(obj: Any, prefix: str) -> Iterator[tuple[str, str]]:
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _strings(item, f"{prefix}[{i}]")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key.startswith("_") or key in SKIP_SUBKEYS:
                continue
            yield from _strings(value, f"{prefix}.{key}")


def iter_publishable(post: dict) -> Iterator[tuple[str, str]]:
    """逐个给出 post.json 里会被发布的文字：(字段路径, 文字)。"""
    for key, value in post.items():
        if key in PUBLISH_KEYS:
            yield from _strings(value, key)
    for i, item in enumerate(post.get("images") or []):
        if not isinstance(item, dict) or item.get("selected") is False:
            continue
        if item.get("on_image_text"):
            yield f"images[{i}].on_image_text", item["on_image_text"]
        for j, layer in enumerate(item.get("text_layers") or []):
            if isinstance(layer, dict) and layer.get("text") and item.get("text_mode") == "底图叠字":
                yield f"images[{i}].text_layers[{j}].text", layer["text"]


def selected_images(post: dict) -> list[dict]:
    return [img for img in (post.get("images") or []) if isinstance(img, dict) and img.get("selected") is not False]


def resolve_file(path_str: str, run: pathlib.Path) -> pathlib.Path | None:
    """原图路径可以是绝对路径、相对工作目录或相对输出目录。"""
    candidates = [pathlib.Path(path_str), pathlib.Path.cwd() / path_str, run / path_str]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def safe_name(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", text).strip("_") or "img"


def find_font(fonts_dir: pathlib.Path | None, wanted: str | None = None) -> str | None:
    """按文件名或风格类别找字体文件，找不到就用默认字体和系统中文字体兜底。"""
    names: list[str] = []
    if wanted:
        names.append(STYLE_TO_FILE.get(wanted, wanted))
    names.append(DEFAULT_FONT_FILE)
    if fonts_dir:
        for name in names:
            cand = fonts_dir / name
            if cand.is_file():
                return str(cand)
    if wanted and os.path.isfile(wanted):
        return wanted
    for cand in SYSTEM_CJK_FONTS:
        if os.path.isfile(cand):
            return cand
    return None
