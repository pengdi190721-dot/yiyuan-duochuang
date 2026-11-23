#!/usr/bin/env python3
"""底图叠字：按 text_layers 在图片上叠中文字。

用法：
  python3 overlay_text.py --image 母版图/x.png --layers layers.json --out 母版图/x_text.png [--fonts-dir yiyuan-data/fonts]

layers.json 可以是 text_layers 列表，也可以是 post.json 里的一个 images 项（读取其中的 text_layers）。
每个图层的字段：
  text          文字，用"｜"或换行分行
  box           [x0, y0, x1, y1]，百分比坐标（左上角 0,0，右下角 100,100）
  size_ratio    字高 ÷ 画面高度，例如 0.065
  color         文字颜色 #RRGGBB
  stroke_color  描边颜色，可省略
  stroke_ratio  描边宽度 ÷ 字号，例如 0.08，可省略
  plate_color   底板颜色，可省略
  plate_alpha   底板不透明度 0–1，0 表示不画底板
  font          字体文件名，或 fonts.md 里的风格类别（如"斜体粗标题"）
  weight        "粗" 时尝试使用粗体
  align         left / center / right
  valign        top / middle / bottom
  line_spacing  行距倍数，默认 1.25
文字放不下时自动缩小字号并按字换行，最小缩到原字号的 40%。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import data_dir, find_font  # noqa: E402

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：python3 -m pip install pillow")


def _rgba(color: str | None, alpha: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(color or "#FFFFFF")[:3]
    return r, g, b, int(round(255 * max(0.0, min(1.0, alpha))))


def _load_font(path: str | None, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not path:
        return ImageFont.load_default()
    font = ImageFont.truetype(path, size)
    if bold:
        try:
            font.set_variation_by_name("Bold")
        except Exception:
            pass
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, stroke: int) -> list[str]:
    lines: list[str] = []
    for para in re.split(r"[｜|\n]", text):
        para = para.strip()
        if not para:
            continue
        cur = ""
        for ch in para:
            trial = cur + ch
            if draw.textlength(trial, font=font) + 2 * stroke <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def draw_layer(img: Image.Image, layer: dict, fonts_dir: pathlib.Path | None) -> Image.Image:
    W, H = img.size
    x0, y0, x1, y1 = [float(v) for v in layer.get("box", [5, 5, 95, 20])]
    bx0, by0, bx1, by1 = int(W * x0 / 100), int(H * y0 / 100), int(W * x1 / 100), int(H * y1 / 100)
    box_w, box_h = max(1, bx1 - bx0), max(1, by1 - by0)
    font_path = find_font(fonts_dir, layer.get("font"))
    bold = layer.get("weight") == "粗"
    start = max(8, int(H * float(layer.get("size_ratio", 0.05))))
    spacing = float(layer.get("line_spacing", 1.25))
    stroke_ratio = float(layer.get("stroke_ratio", 0) or 0)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    size = start
    while True:
        font = _load_font(font_path, size, bold)
        stroke = int(round(size * stroke_ratio)) if layer.get("stroke_color") else 0
        lines = _wrap(draw, layer.get("text", ""), font, box_w, stroke)
        line_h = int(size * spacing)
        total_h = line_h * len(lines)
        widest = max((draw.textlength(l, font=font) for l in lines), default=0) + 2 * stroke
        if (total_h <= box_h and widest <= box_w) or size <= max(8, int(start * 0.4)):
            break
        size = int(size * 0.95)

    align = layer.get("align", "center")
    valign = layer.get("valign", "middle")
    top = by0 if valign == "top" else (by1 - total_h if valign == "bottom" else by0 + (box_h - total_h) // 2)

    plate_alpha = float(layer.get("plate_alpha", 0) or 0)
    if plate_alpha > 0 and lines:
        pad = int(size * 0.25)
        if align == "left":
            px0 = bx0
        elif align == "right":
            px0 = bx1 - int(widest)
        else:
            px0 = bx0 + (box_w - int(widest)) // 2
        draw.rounded_rectangle([px0 - pad, top - pad, px0 + int(widest) + pad, top + total_h + pad],
                               radius=pad, fill=_rgba(layer.get("plate_color", "#000000"), plate_alpha))

    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        if align == "left":
            x = bx0 + stroke
        elif align == "right":
            x = bx1 - lw - stroke
        else:
            x = bx0 + (box_w - lw) / 2
        y = top + i * line_h + (line_h - size) / 2
        draw.text((x, y), line, font=font, fill=_rgba(layer.get("color", "#FFFFFF")),
                  stroke_width=stroke, stroke_fill=_rgba(layer.get("stroke_color", "#000000")))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def overlay(img: Image.Image, layers: list[dict], fonts_dir: pathlib.Path | None) -> Image.Image:
    out = img.convert("RGBA")
    for layer in layers:
        if isinstance(layer, dict) and layer.get("text"):
            out = draw_layer(out, layer, fonts_dir)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True)
    ap.add_argument("--layers", required=True, help="text_layers 的 JSON 文件")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts-dir", help="字体目录，默认 ./yiyuan-data/fonts")
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.layers).read_text(encoding="utf-8"))
    layers = data.get("text_layers", []) if isinstance(data, dict) else data
    fonts_dir = pathlib.Path(args.fonts_dir) if args.fonts_dir else data_dir(None) / "fonts"
    with Image.open(args.image) as im:
        result = overlay(im, layers, fonts_dir)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in (".jpg", ".jpeg"):
        result.convert("RGB").save(out, quality=95)
    else:
        result.save(out)
    print(f"已叠字：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
