"""
extend.py — 정사각 시황 그림을 1080x1920 세로 화면으로 늘린다.
위는 그림 맨 윗줄 색이 하늘처럼 그대로 이어지고, 아래는 그림 맨 아랫줄 색이 그대로 이어진다.
(예전의 흐린 배경 대신, 그림과 같은 색으로 이어 붙이는 방식. 쓰는 곳: insta.py video)
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

W, H = 1080, 1920


def _smooth(row: np.ndarray, k: int = 81) -> np.ndarray:
    ker = np.ones(k) / k
    return np.stack([np.convolve(np.pad(row[:, c], (k // 2, k // 2), mode="edge"), ker, "valid") for c in range(3)], 1)


def _fill_corners(a: np.ndarray, top: bool) -> np.ndarray:
    """그림 네 모서리의 둥근 바깥 회색 자리를 찾아 반환 (모서리에 붙은 덩어리만)."""
    h, w, _ = a.shape
    n = 110
    out = np.zeros((h, w), bool)
    for left in (True, False):
        ys = slice(0, n) if top else slice(h - n, h)
        xs = slice(0, n) if left else slice(w - n, w)
        blk = a[ys, xs]
        cy, cx = (0 if top else n - 1), (0 if left else n - 1)
        ref = blk[cy, cx]
        m = np.abs(blk - ref).sum(2) < 12
        lab, _ = ndimage.label(m)
        if lab[cy, cx]:
            comp = lab == lab[cy, cx]
            comp = ndimage.binary_dilation(comp, iterations=2)
            out[ys, xs] |= comp
    return out


def extend(src: str, out: str, sky_top=None) -> None:
    im = Image.open(src).convert("RGB")
    h0 = round(im.height * W / im.width)
    a = np.array(im.resize((W, h0), Image.LANCZOS)).astype(float)
    a = a[4:h0 - 3]                      # 그림 맨 바깥 1~2px 흰 테두리 선은 잘라낸다
    h0 = a.shape[0]
    y0 = (H - h0) // 2
    ybot = y0 + h0

    # 위·아래 가장자리 색: 가운데 열들의 색을 대표로 쓴다 (모서리·달력 아이콘 같은 데에 안 휘둘리게)
    def edge(rows):
        r = a[rows].mean(0)
        r = r.copy()
        r[:160] = r[160]
        r[W - 160:] = r[W - 161]
        return _smooth(r, 201)

    top_s = edge(slice(4, 8))
    bot_s = edge(slice(h0 - 6, h0 - 3))
    top_c, bot_c = np.median(top_s, 0), np.median(bot_s, 0)
    # 둥근 모서리의 바깥 회색 자리는 같은 가장자리 색으로 메운다
    for m, c, sl in ((_fill_corners(a, True), top_c, slice(0, 110)), (_fill_corners(a, False), bot_c, slice(h0 - 110, h0))):
        sub = a[sl]
        sub[m[sl]] = c
        a[sl] = sub
    top_edge, bot_edge = top_s, bot_s

    canvas = np.zeros((H, W, 3))
    tgt = np.array(sky_top if sky_top is not None else top_s.mean(0) * np.array([0.80, 0.90, 0.98]))
    for y in range(y0):
        d = y0 - 1 - y                                        # 그림에서 위로 떨어진 거리
        t = (d / max(y0 - 1, 1)) ** 0.9
        near = max(0.0, 1 - d / 90.0)                          # 이음매 근처는 그림 맨 윗줄 그대로
        base = top_s * (1 - t) + tgt * t
        canvas[y] = base * (1 - near) + top_edge * near
    btgt = bot_s.mean(0) * 0.97
    for y in range(ybot, H):
        d = y - ybot
        t = (d / max(H - ybot - 1, 1)) ** 1.2
        near = max(0.0, 1 - d / 90.0)
        base = bot_s * (1 - t) + btgt * t
        canvas[y] = base * (1 - near) + bot_edge * near

    # 윗부분 구름 (그림 속 하늘의 말랑한 구름 느낌, 이음매 쪽으로 갈수록 사라짐)
    rng = np.random.default_rng(7)
    cl = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(cl)
    for _ in range(7):
        cx, cy = int(rng.integers(-40, W + 40)), int(rng.integers(60, max(80, y0 - 120)))
        for _ in range(6):
            rx, ry = int(rng.integers(60, 150)), int(rng.integers(26, 52))
            ox, oy = int(rng.integers(-120, 120)), int(rng.integers(-22, 22))
            d.ellipse([cx + ox - rx, cy + oy - ry, cx + ox + rx, cy + oy + ry], fill=int(rng.integers(150, 230)))
    cl = cl.filter(ImageFilter.GaussianBlur(14))
    fade = np.clip((y0 - 90 - np.arange(H)) / 140.0, 0, 1)[:, None] * (np.arange(H) < y0)[:, None]
    alpha = (np.array(cl).astype(float) / 255 * 0.7 * fade)[..., None]
    canvas = canvas * (1 - alpha) + 255 * alpha

    canvas[y0:ybot] = a
    Image.fromarray(np.clip(canvas, 0, 255).astype("uint8")).save(out)


if __name__ == "__main__":
    import sys
    extend(sys.argv[1], sys.argv[2])


# ───────────────────────────────────────────────────────────────────────────
# compose — 확정된 세로 화면(시안 3): 카드를 줄여 가운데에 두고
#   위는 큰 숫자 한 줄 + 날짜·분위기 한 줄, 아래는 캐릭터 + 팔로우 문구 한 줄
# ───────────────────────────────────────────────────────────────────────────
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto", "/usr/share/fonts/noto-cjk"]


def _font(weight: str, size: int):
    from PIL import ImageFont
    for d in _FONT_DIRS:
        p = os.path.join(d, f"NotoSansCJK-{weight}.ttc")
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _lerp(c1, c2, t):
    return tuple(c1[i] * (1 - t) + c2[i] * t for i in range(3))


def compose(src: str, out: str, headline: str, sub: str, foot1: str = "팔로우하고 매일 확인해요",
            foot2: str = "@stock_burger_king", scale: float = 0.9) -> None:
    # 배경: 위는 진한 하늘색 → 아래는 옅은 회색 (이음매가 없도록 한 번에 그라데이션)
    stops = [(0.0, (46, 156, 250)), (0.55, (120, 195, 252)), (0.80, (226, 238, 250)), (1.0, (242, 244, 246))]
    ys = np.linspace(0, 1, H)
    col = np.zeros((H, 3))
    for i in range(len(stops) - 1):
        (a0, c0), (a1, c1) = stops[i], stops[i + 1]
        m = (ys >= a0) & (ys <= a1)
        t = ((ys[m] - a0) / (a1 - a0))[:, None]
        col[m] = np.array(c0) * (1 - t) + np.array(c1) * t
    canvas = np.repeat(col[:, None, :], W, axis=1)

    # 위쪽 옅은 구름
    rng = np.random.default_rng(7)
    cl = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(cl)
    for _ in range(7):
        cx, cy = int(rng.integers(-40, W + 40)), int(rng.integers(40, 300))
        for _ in range(6):
            rx, ry = int(rng.integers(60, 150)), int(rng.integers(26, 52))
            ox, oy = int(rng.integers(-120, 120)), int(rng.integers(-22, 22))
            d.ellipse([cx + ox - rx, cy + oy - ry, cx + ox + rx, cy + oy + ry], fill=int(rng.integers(150, 230)))
    cl = cl.filter(ImageFilter.GaussianBlur(14))
    fade = np.clip((520 - np.arange(H)) / 260.0, 0, 1)[:, None]
    al = (np.array(cl).astype(float) / 255 * 0.6 * fade)[..., None]
    canvas = canvas * (1 - al) + 255 * al
    base = Image.fromarray(np.clip(canvas, 0, 255).astype("uint8")).convert("RGBA")

    # 카드(줄여서 가운데, 둥근 모서리 + 그림자)
    card = Image.open(src).convert("RGB")
    nw = int(W * scale)
    nh = round(card.height * nw / card.width)
    card = card.resize((nw, nh), Image.LANCZOS)
    cx, cy = (W - nw) // 2, (H - nh) // 2 + 10
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((cx, cy + 8, cx + nw, cy + nh + 8), 36, fill=(10, 30, 80, 60))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    mk = Image.new("L", card.size, 0)
    ImageDraw.Draw(mk).rounded_rectangle((0, 0, nw, nh), 36, fill=255)
    base.paste(card, (cx, cy), mk)

    d = ImageDraw.Draw(base)
    size = 120
    f = _font("Black", size)
    while d.textlength(headline, font=f) > W - 100 and size > 60:       # 긴 제목은 폭에 맞춰 줄임
        size -= 6
        f = _font("Black", size)
    d.text(((W - d.textlength(headline, font=f)) / 2, cy - 230), headline, font=f, fill=(255, 255, 255))
    f2 = _font("Bold", 38)
    d.text(((W - d.textlength(sub, font=f2)) / 2, cy - 82), sub, font=f2, fill=(240, 248, 255))

    ch = Image.open(os.path.join(_HERE, "..", "assets", "ui", "follow.png")).convert("RGBA")
    ch.thumbnail((250, 250), Image.LANCZOS)
    by = cy + nh + 40
    base.alpha_composite(ch, (90, by))
    d.text((380, by + 30), foot1, font=_font("Black", 44), fill=(20, 45, 110))
    d.text((380, by + 95), foot2, font=_font("Bold", 32), fill=(70, 85, 110))
    base.convert("RGB").save(out)
