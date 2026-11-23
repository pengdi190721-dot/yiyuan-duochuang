#!/usr/bin/env python3
"""第 ⑦ 步：按 post.json 的 images 调用 image2.6 生成图片。

用法：
  python3 gen_image.py --run "输出/2026-11-23_主题" --platform xiaohongshu
  python3 gen_image.py --run ... --platform xiaohongshu --slot 封面      # 只重做这一张
  python3 gen_image.py --run ... --platform xiaohongshu --dry-run        # 只看提示词，不调接口

做的事：
  1. 按固定模板拼提示词（模型不改模板）。
  2. 有参考原图走 edit 接口（图生图），没有走 generate 接口；尺寸取 image.json 里该比例的最大一档，不支持就退到下一档。
  3. 原样保存接口返回的图片到 母版图/（不改动、不压缩，保留隐式标识）。
  4. 底图叠字模式：调用 overlay_text.py 叠字。
  5. 按平台比例居中裁切、只缩不放，右下角加"AI 生成"，导出到 <平台目录>/图片/NN_<slot>.jpg。
  6. 每张图记一行 images.csv。
配置：yiyuan-data/config/image.json；API Key 只从环境变量 IMAGE_API_KEY 读取。
"""
from __future__ import annotations

import argparse
import base64
import csv
import importlib.util
import io
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PLATFORMS, TARGET_PX, check_platform, data_dir, find_font, load_json, now,
    platform_dir, post_path, ratio_value, resolve_file, safe_name, selected_images,
)

TEMPLATE_TEXT = (
    "以参考图为基础，重新设计一张{platform}{slot}图片，比例 {ratio}，最高清。\n"
    "必须保留：{keep}。只允许改动：{change}。\n"
    "在画面{text_area}写出以下文字，逐字照写，不增不减：「{on_image_text}」。\n"
    "整体风格：{style}。\n"
    "不要新增参考图里没有的设施、景观、菜品和人物；不要出现其他文字、水印和 Logo。"
)
TEMPLATE_BASE = (
    "以参考图为基础，重新设计一张{platform}{slot}底图，比例 {ratio}，最高清。\n"
    "必须保留：{keep}。只允许改动：{change}。\n"
    "在画面{text_area}留出干净、低对比的区域，用于后期加字。\n"
    "整体风格：{style}。画面中不要出现任何文字、水印和 Logo。\n"
    "不要新增参考图里没有的设施、景观、菜品和人物。"
)
CSV_FIELDS = ["time", "platform", "slot", "file", "master", "reference_images", "text_mode", "font",
              "model", "size", "status", "note", "retry", "prompt"]


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def build_prompt(item: dict, platform_name: str) -> str:
    template = TEMPLATE_BASE if item.get("text_mode") == "底图叠字" else TEMPLATE_TEXT
    text = template.format(
        platform=platform_name, slot=item.get("slot", ""), ratio=item.get("ratio", ""),
        keep=item.get("keep") or "画面主体", change=item.get("change") or "构图、色调、排版",
        text_area=item.get("text_area") or "合适位置", on_image_text=item.get("on_image_text") or "",
        style=item.get("style") or "清新实拍风",
    )
    if not item.get("reference_images"):
        lines = []
        for line in text.split("\n"):
            if line.startswith("必须保留："):
                line = line.split("。", 1)[1] if "。" in line else ""
            line = line.replace("以参考图为基础，", "")
            if line:
                lines.append(line)
        text = "\n".join(lines)
    return text


def _post_json(url: str, key: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return _send(req, timeout)


def _post_multipart(url: str, key: str, fields: dict, files: list[tuple[str, pathlib.Path]], timeout: int) -> dict:
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in fields.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    for name, path in files:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n"
                  f"Content-Type: {ctype}\r\n\r\n".encode("utf-8"))
        buf.write(path.read_bytes())
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode("utf-8"))
    req = urllib.request.Request(url, data=buf.getvalue(), method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    return _send(req, timeout)


def _send(req: urllib.request.Request, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise ApiError(err.code, err.read().decode("utf-8", "replace")) from None


def _image_bytes(resp: dict, timeout: int) -> bytes:
    items = resp.get("data") or resp.get("images") or []
    if not items:
        raise ApiError(0, f"接口没有返回图片：{json.dumps(resp, ensure_ascii=False)[:300]}")
    first = items[0]
    b64 = first.get("b64_json") or first.get("b64") or first.get("image_base64")
    if b64:
        return base64.b64decode(b64)
    url = first.get("url")
    if url:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    raise ApiError(0, f"无法识别返回格式：{json.dumps(first, ensure_ascii=False)[:300]}")


def call_api(cfg: dict, key: str, prompt: str, size: str, refs: list[pathlib.Path]) -> bytes:
    base = cfg["base_url"].rstrip("/")
    timeout = int(cfg.get("timeout_seconds", 300))
    size_field = cfg.get("size_field", "size")
    fields = {"model": cfg["model"], "prompt": prompt, size_field: size, "n": 1}
    fields.update(cfg.get("extra") or {})
    if refs:
        files = [(cfg.get("image_field", "image[]"), p) for p in refs]
        resp = _post_multipart(base + cfg.get("edit_path", "/v1/images/edits"), key, fields, files, timeout)
    else:
        resp = _post_json(base + cfg.get("generate_path", "/v1/images/generations"), key, fields, timeout)
    return _image_bytes(resp, timeout)


def generate(cfg: dict, key: str, prompt: str, ratio: str, refs: list[pathlib.Path]) -> tuple[bytes, str]:
    sizes = (cfg.get("sizes") or {}).get(ratio) or []
    if not sizes:
        raise ApiError(0, f"image.json 的 sizes 里没有比例 {ratio}")
    last: Exception | None = None
    for size in sizes:
        try:
            return call_api(cfg, key, prompt, size, refs), size
        except ApiError as err:
            last = err
            if err.status in (401, 403):
                raise ApiError(err.status, "鉴权失败：检查环境变量 IMAGE_API_KEY 和 image.json 的 base_url") from None
            body = err.body.lower()
            if err.status in (400, 422) and ("size" in body or "尺寸" in body or "resolution" in body):
                print(f"    尺寸 {size} 不支持，换下一档")
                continue
            raise
    raise last or ApiError(0, "所有尺寸都失败")


def _ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def export(src, ratio: str, fonts_dir: pathlib.Path, out: pathlib.Path) -> tuple[int, int, bool]:
    from PIL import Image, ImageDraw, ImageFont
    img = src.convert("RGB")
    W, H = img.size
    want = ratio_value(ratio)
    if W / H > want:
        nw = int(round(H * want))
        img = img.crop(((W - nw) // 2, 0, (W - nw) // 2 + nw, H))
    elif W / H < want:
        nh = int(round(W / want))
        img = img.crop((0, (H - nh) // 2, W, (H - nh) // 2 + nh))
    tw, th = TARGET_PX[ratio]
    below = img.size[0] < tw or img.size[1] < th
    if not below:
        img = img.resize((tw, th), Image.LANCZOS)
    # 右下角"AI 生成"显式标识
    W, H = img.size
    label = "AI 生成"
    size = max(14, int(H * 0.018))
    font_path = find_font(fonts_dir, None)
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tw_ = d.textlength(label, font=font)
    pad, margin = int(size * 0.35), int(W * 0.015)
    x1, y1 = W - margin, H - margin
    x0, y0 = x1 - tw_ - 2 * pad, y1 - size - 2 * pad
    d.rounded_rectangle([x0, y0, x1, y1], radius=pad, fill=(0, 0, 0, 115))
    d.text((x0 + pad, y0 + pad - size * 0.1), label, font=font, fill=(255, 255, 255, 235))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    exif = Image.Exif()
    exif[0x010E] = "AIGC: AI-generated image (yiyuan-duochuang)"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95, exif=exif.tobytes())
    return img.size[0], img.size[1], below


def log_row(run: pathlib.Path, row: dict) -> None:
    path = run / "images.csv"
    new = not path.exists()
    with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def retries_so_far(run: pathlib.Path, platform: str, slot: str) -> int:
    path = run / "images.csv"
    if not path.exists():
        return 0
    with open(path, encoding="utf-8-sig") as fh:
        return sum(1 for r in csv.DictReader(fh) if r.get("platform") == platform and r.get("slot") == slot)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--slot", help="只生成这一张（slot 名）")
    ap.add_argument("--data-dir", help="用户数据目录，默认 ./yiyuan-data")
    ap.add_argument("--dry-run", action="store_true", help="只打印提示词，不调接口")
    args = ap.parse_args()

    code = check_platform(args.platform)
    run = pathlib.Path(args.run)
    post = load_json(post_path(run, code))
    ddir = data_dir(args.data_dir)
    fonts_dir = ddir / "fonts"
    cfg_path = ddir / "config" / "image.json"
    cfg = load_json(cfg_path) if cfg_path.exists() else {}
    key = os.environ.get("IMAGE_API_KEY", "")
    if not args.dry_run:
        if not cfg.get("base_url") or "你的" in cfg.get("base_url", ""):
            sys.exit(f"先在 {cfg_path} 填好 base_url 和 model（首次运行第 2 步）")
        if not key:
            sys.exit("没有设置环境变量 IMAGE_API_KEY（首次运行第 2 步）")
        if importlib.util.find_spec("PIL") is None:
            sys.exit("需要 Pillow：python3 -m pip install pillow")

    pname = PLATFORMS[code]["name"]
    items = selected_images(post)
    failures = 0
    for idx, item in enumerate(items, start=1):
        slot = str(item.get("slot") or idx)
        if args.slot and slot != args.slot:
            continue
        prompt = build_prompt(item, pname)
        refs = []
        for ref in item.get("reference_images") or []:
            found = resolve_file(ref, run)
            if found is None:
                print(f"  [{slot}] 找不到参考原图 {ref}，跳过这一张")
                failures += 1
                refs = None
                break
            refs.append(found)
        if refs is None:
            continue
        ratio = item.get("ratio", "3:4")
        print(f"[{pname} · {slot}] 比例 {ratio}，参考图 {len(refs)} 张，文字模式 {item.get('text_mode')}")
        if args.dry_run:
            sizes = (cfg.get("sizes") or {}).get(ratio, [])
            print(f"  将使用尺寸：{sizes[0] if sizes else '（image.json 未配置）'}")
            print("  提示词：\n    " + prompt.replace("\n", "\n    "))
            continue

        from PIL import Image
        retry = retries_so_far(run, code, slot)
        try:
            data, size = generate(cfg, key, prompt, ratio, refs)
        except Exception as err:  # noqa: BLE001
            print(f"  失败：{err}")
            log_row(run, {"time": now(), "platform": code, "slot": slot, "status": "failed", "note": str(err)[:200],
                          "retry": retry, "prompt": prompt, "model": cfg.get("model", "")})
            failures += 1
            continue
        master = run / "母版图" / f"{code}_{idx:02d}_{safe_name(slot)}{_ext(data)}"
        master.parent.mkdir(parents=True, exist_ok=True)
        master.write_bytes(data)
        img = Image.open(io.BytesIO(data))
        img.load()
        font_used = "NotoSansSC.ttf"
        if item.get("text_mode") == "底图叠字" and item.get("text_layers"):
            from overlay_text import overlay
            img = overlay(img, item["text_layers"], fonts_dir)
            font_used = ";".join(sorted({str(l.get("font", "")) for l in item["text_layers"] if isinstance(l, dict)}))
            img.save(master.with_name(master.stem + "_叠字.png"))
        out = platform_dir(run, code) / "图片" / f"{idx:02d}_{safe_name(slot)}.jpg"
        w, h, below = export(img, ratio, fonts_dir, out)
        note = "below_target" if below else ""
        print(f"  母版图 {master.name}（{size}），导出 {out.name}（{w}×{h}）{'，分辨率低于平台建议' if below else ''}")
        log_row(run, {"time": now(), "platform": code, "slot": slot, "file": str(out.relative_to(run)),
                      "master": str(master.relative_to(run)), "reference_images": ";".join(str(r) for r in refs),
                      "text_mode": item.get("text_mode", ""), "font": font_used, "model": cfg.get("model", ""),
                      "size": size, "status": "ok", "note": note, "retry": retry, "prompt": prompt})
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
