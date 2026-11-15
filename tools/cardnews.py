"""버거대왕 카드뉴스 생성기.

글(무슨 말을 할지)은 JSON 한 장에 적고, 이 프로그램이 정해진 틀로 1080x1350 카드를 찍어낸다.
틀은 항상 같다:  1장 = 빨간 큰 글씨 + 버거대왕 표정  /  가운데 장 = 위 그림 + 아래 검정 한 줄 + 파란 굵은 두 줄
               /  마지막 장 = 버거대왕 마무리.   배경은 항상 흰색.

쓰는 법:  python tools/cardnews.py cards/2026-11-15-nvda/spec.json            (카드 PNG 생성)
          python tools/cardnews.py cards/2026-11-15-nvda/spec.json --reel     (카드를 넘기는 릴스 mp4 도 같이)

spec.json 모양:
{
  "cover":  {"title": ["엔비디아", "선장 교체"], "char": "bd23_속보", "sub": "삼전·하닉은 어떻게 되나"},
  "slides": [
    {"visual": {"type": "char", "name": "bd03_급락멘붕"},                       "top": "...", "main": ["...", "..."], "note": "출처"},
    {"visual": {"type": "line", "title": "...", "points": [..], "labels": [..], "unit": "달러"}, ...},
    {"visual": {"type": "bars", "items": [["이름", 값, "표시글자"], ...]}, ...},
    {"visual": {"type": "big",  "big": "-4.34%", "label": "엔비디아 12일 종가", "color": "blue"}, ...},
    {"visual": {"type": "list", "title": "이번 주 일정", "rows": [["17일(화)", "엔비디아 실적"], ...]}, ...}
  ],
  "outro":  {"title": ["버거대왕", "팔로우"], "char": "bd25_팔로우부탁", "sub": "매일 장 마감 뒤 올라옵니다"},
  "mood": "down"
}
"""
from __future__ import annotations
import glob, hashlib, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H = 1080, 1350
RED, BLUE, INK, GREY, LINE = "#E8281E", "#1E50C8", "#111111", "#8A8A8A", "#E6E6E6"
UP, DOWN = "#E8281E", "#1E50C8"            # 한국식: 오르면 빨강, 내리면 파랑
FONT_DIRS = ["/usr/share/fonts/opentype/noto", os.path.join(ROOT, "assets", "fonts")]


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        p = os.path.join(d, f"NotoSansCJK-{weight}.ttc")
        if os.path.exists(p):
            return ImageFont.truetype(p, size, index=1)          # index 1 = 한국어 글꼴
        p = os.path.join(d, f"NotoSansKR-{weight}.otf")
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise SystemExit("Noto Sans CJK 글꼴이 없어요 (assets/fonts 에 넣거나 fonts-noto-cjk 설치)")


def fit(dr, lines, weight, size, maxw, floor=40):
    """가장 긴 줄이 maxw 안에 들어올 때까지 글자 크기를 줄인다."""
    while size > floor:
        f = font(weight, size)
        if max(dr.textlength(l, font=f) for l in lines) <= maxw:
            return f, size
        size -= 2
    return font(weight, floor), floor


def center(dr, y, text, f, fill):
    dr.text(((W - dr.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


def character(name: str, box: int, cut_bg: bool) -> Image.Image:
    """캐릭터 그림을 불러온다. cut_bg 면 가장자리 배경색을 투명하게 뺀다(흰 바탕에 그대로 얹으려고)."""
    p = os.path.join(ROOT, "assets", "characters", name + ".png")
    if not os.path.exists(p):
        c = sorted(glob.glob(os.path.join(ROOT, "assets", "characters", name.split("_")[0] + "*.png")))
        if not c:
            raise SystemExit(f"캐릭터 그림 없음: {name}")
        p = c[0]
    im = Image.open(p).convert("RGB")
    if cut_bg:
        key = (255, 0, 255)
        w, h = im.size
        for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2), (w - 1, h // 2)]:
            if im.getpixel(xy) != key:
                ImageDraw.floodfill(im, xy, key, thresh=38)
        rgba = im.convert("RGBA")
        px = rgba.load()
        for y in range(h):
            for x in range(w):
                if px[x, y][:3] == key:
                    px[x, y] = (255, 255, 255, 0)
        im = rgba.crop(rgba.getchannel("A").getbbox())
    else:
        im = im.convert("RGBA")
    im.thumbnail((box, box), Image.LANCZOS)
    return im


def page_no(dr, i, n):
    f = font("Bold", 26)
    t = f"{i}/{n}"
    dr.text((W - 60 - dr.textlength(t, font=f), 44), t, font=f, fill="#B5B5B5")
    dr.text((60, 44), "버거대왕", font=f, fill="#B5B5B5")


# ───────── 가운데 장의 위쪽 그림 (x 60~1020, y 110~810) ─────────
VX0, VY0, VX1, VY1 = 60, 110, 1020, 810


def v_char(c, dr, v):
    im = character(v["name"], 700, cut_bg=False)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=36, fill=255)
    c.paste(im, ((W - im.width) // 2, VY0), mask)


def v_big(c, dr, v):
    col = {"red": UP, "blue": DOWN, "black": INK}.get(v.get("color", "black"), INK)
    dr.rounded_rectangle((VX0, VY0, VX1, VY1), radius=36, fill="#F5F5F5")
    f, s = fit(dr, [v["big"]], "Black", 250, VX1 - VX0 - 100, 90)
    bb = dr.textbbox((0, 0), v["big"], font=f)
    y = (VY0 + VY1) / 2 - (bb[3] + bb[1]) / 2 - (30 if v.get("label") else 0)
    center(dr, y, v["big"], f, col)
    if v.get("label"):
        fl, _ = fit(dr, [v["label"]], "Bold", 44, VX1 - VX0 - 100, 28)
        center(dr, y + bb[3] + 34, v["label"], fl, "#555555")
    if v.get("head"):
        fh, _ = fit(dr, [v["head"]], "Bold", 44, VX1 - VX0 - 100, 28)
        center(dr, VY0 + 48, v["head"], fh, "#555555")


def v_line(c, dr, v):
    pts = [float(p) for p in v["points"]]
    labels = v.get("labels") or [""] * len(pts)
    dr.rounded_rectangle((VX0, VY0, VX1, VY1), radius=36, fill="#F5F5F5")
    if v.get("title"):
        ft, _ = fit(dr, [v["title"]], "Bold", 40, VX1 - VX0 - 100, 26)
        dr.text((VX0 + 50, VY0 + 36), v["title"], font=ft, fill="#444444")
    x0, x1, y0, y1 = VX0 + 80, VX1 - 80, VY0 + 170, VY1 - 110
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    xy = [(x0 + (x1 - x0) * i / (len(pts) - 1), y1 - (y1 - y0) * (p - lo) / span) for i, p in enumerate(pts)]
    col = UP if pts[-1] >= pts[0] else DOWN
    dr.line(xy, fill=col, width=10, joint="curve")
    fv, fl = font("Black", 38), font("Bold", 30)
    unit = v.get("unit", "")
    show = set(v.get("show") or [0, len(pts) - 1, pts.index(hi), pts.index(lo)])
    for i, (x, y) in enumerate(xy):
        dr.ellipse((x - 12, y - 12, x + 12, y + 12), fill=col, outline="white", width=4)
        if i in show:
            t = f"{pts[i]:,.2f}".rstrip("0").rstrip(".") if pts[i] % 1 else f"{pts[i]:,.0f}"
            t += unit
            tw = dr.textlength(t, font=fv)
            tx = min(max(x - tw / 2, VX0 + 20), VX1 - 20 - tw)
            ty = y - 64 if pts[i] >= (lo + hi) / 2 else y + 22
            dr.text((tx, ty), t, font=fv, fill=INK)
        if labels[i]:
            tw = dr.textlength(labels[i], font=fl)
            dr.text((min(max(x - tw / 2, VX0 + 20), VX1 - 20 - tw), VY1 - 78), labels[i], font=fl, fill="#666666")


def v_bars(c, dr, v):
    items = v["items"]
    dr.rounded_rectangle((VX0, VY0, VX1, VY1), radius=36, fill="#F5F5F5")
    if v.get("title"):
        ft, _ = fit(dr, [v["title"]], "Bold", 40, VX1 - VX0 - 100, 26)
        dr.text((VX0 + 50, VY0 + 36), v["title"], font=ft, fill="#444444")
    n = len(items)
    top, base = VY0 + 200, VY1 - 110
    mx = max(abs(float(it[1])) for it in items) or 1
    slot = (VX1 - VX0 - 120) / n
    bw = min(slot * 0.56, 220)
    fv, fl = font("Black", 42), font("Bold", 32)
    for i, it in enumerate(items):
        name, val = it[0], float(it[1])
        txt = it[2] if len(it) > 2 else f"{val:,.0f}"
        col = it[3] if len(it) > 3 else ("grey" if i < n - 1 else "red")
        col = {"red": UP, "blue": DOWN, "grey": "#BDBDBD", "black": INK}.get(col, col)
        cx = VX0 + 60 + slot * (i + .5)
        h = (base - top) * abs(val) / mx
        dr.rounded_rectangle((cx - bw / 2, base - h, cx + bw / 2, base), radius=10, fill=col)
        fvv, _ = fit(dr, [txt], "Black", 42, slot - 12, 24)
        dr.text((cx - dr.textlength(txt, font=fvv) / 2, base - h - 62), txt, font=fvv, fill=INK)
        fll, _ = fit(dr, [name], "Bold", 32, slot - 12, 20)
        dr.text((cx - dr.textlength(name, font=fll) / 2, base + 22), name, font=fll, fill="#555555")


def v_list(c, dr, v):
    rows = v["rows"]
    dr.rounded_rectangle((VX0, VY0, VX1, VY1), radius=36, fill="#F5F5F5")
    y = VY0 + 44
    if v.get("title"):
        ft, _ = fit(dr, [v["title"]], "Black", 50, VX1 - VX0 - 100, 30)
        dr.text((VX0 + 56, y), v["title"], font=ft, fill=INK)
        y += 104
    room = VY1 - 40 - y
    rh = min(room / len(rows), 128)
    fk = font("Black", 40)
    kw = max(dr.textlength(r[0], font=fk) for r in rows) + 40
    for i, r in enumerate(rows):
        yy = y + rh * i
        if i:
            dr.line((VX0 + 56, yy, VX1 - 56, yy), fill="#DDDDDD", width=2)
        col = {"red": UP, "blue": DOWN}.get(r[2] if len(r) > 2 else "", BLUE)
        dr.text((VX0 + 56, yy + rh / 2 - 30), r[0], font=fk, fill=col)
        fvv, _ = fit(dr, [r[1]], "Bold", 40, VX1 - 56 - (VX0 + 56 + kw), 24)
        dr.text((VX0 + 56 + kw, yy + rh / 2 - 30), r[1], font=fvv, fill=INK)


VISUALS = {"char": v_char, "big": v_big, "line": v_line, "bars": v_bars, "list": v_list}


# ───────── 장 종류 ─────────
def cover(spec, n) -> Image.Image:
    cv = spec["cover"]
    c = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(c)
    title = cv["title"] if isinstance(cv["title"], list) else [cv["title"]]
    f, s = fit(dr, title, "Black", 300 if len(title) == 1 else 220, W - 110, 110)
    y = 70
    for l in title:
        bb = dr.textbbox((0, 0), l, font=f)
        center(dr, y - bb[1], l, f, RED)
        y += (bb[3] - bb[1]) + int(s * 0.16)
    if cv.get("sub"):
        fs, ss = fit(dr, [cv["sub"]], "Black", 64, W - 140, 36)
        center(dr, y + 6, cv["sub"], fs, INK)
        y += ss + 40
    room = H - y - 10
    im = character(cv.get("char", "bd23_속보"), min(room, 980), cut_bg=True)
    c.paste(im, ((W - im.width) // 2, H - im.height), im)
    return c


def body(sl, i, n) -> Image.Image:
    c = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(c)
    page_no(dr, i, n)
    v = sl.get("visual") or {"type": "char", "name": "bd10_차분관망"}
    VISUALS[v["type"]](c, dr, v)
    main = sl["main"] if isinstance(sl["main"], list) else [sl["main"]]
    ft, st = fit(dr, [sl["top"]], "Medium", 62, W - 120, 36)
    fm, sm = fit(dr, main, "Black", 86, W - 100, 44)
    gap = int(sm * 1.22)
    total = st + 34 + gap * len(main)
    bottom = H - (84 if sl.get("note") else 50)
    y = VY1 + 40 + max(0, (bottom - (VY1 + 40) - total) // 2)
    bb = dr.textbbox((0, 0), sl["top"], font=ft)
    center(dr, y - bb[1], sl["top"], ft, INK)
    y += st + 34
    for l in main:
        bb = dr.textbbox((0, 0), l, font=fm)
        center(dr, y - bb[1], l, fm, sl.get("color") and {"red": RED, "blue": BLUE}[sl["color"]] or BLUE)
        y += gap
    if sl.get("note"):
        fn, _ = fit(dr, [sl["note"]], "Regular", 24, W - 100, 16)
        center(dr, H - 52, sl["note"], fn, GREY)
    return c


def outro(spec, n) -> Image.Image:
    o = spec.get("outro") or {}
    c = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(c)
    title = o.get("title") or ["버거대왕", "팔로우"]
    f, s = fit(dr, title, "Black", 230, W - 120, 100)
    y = 70
    for l in title:
        bb = dr.textbbox((0, 0), l, font=f)
        center(dr, y - bb[1], l, f, INK)
        y += (bb[3] - bb[1]) + int(s * 0.16)
    sub = o.get("sub", "매일 장 마감 뒤 올라옵니다")
    fs, ss = fit(dr, [sub], "Bold", 48, W - 140, 30)
    center(dr, y + 4, sub, fs, "#555555")
    y += ss + 36
    im = character(o.get("char", "bd25_팔로우부탁"), min(H - y - 60, 900), cut_bg=True)
    c.paste(im, ((W - im.width) // 2, H - im.height - 50), im)
    fn = font("Regular", 22)
    center(dr, H - 42, "개인 기록이며 매수·매도 권유가 아닙니다. 투자 판단과 책임은 본인에게 있습니다.", fn, GREY)
    return c


def check(spec) -> list[str]:
    """틀이 무너지는 글을 미리 잡는다."""
    bad = []
    if not 4 <= len(spec["slides"]) <= 8:
        bad.append(f"가운데 장은 4~8장 (지금 {len(spec['slides'])}장)")
    for i, sl in enumerate(spec["slides"], 2):
        if len(sl["top"]) > 18:
            bad.append(f"{i}장 윗줄이 깁니다({len(sl['top'])}자, 18자 이내)")
        main = sl["main"] if isinstance(sl["main"], list) else [sl["main"]]
        if len(main) > 2:
            bad.append(f"{i}장 굵은 줄은 2줄까지")
        for l in main:
            if len(l) > 15:
                bad.append(f"{i}장 굵은 줄이 깁니다({len(l)}자, 15자 이내): {l}")
        if sl.get("visual", {}).get("type") not in VISUALS:
            bad.append(f"{i}장 그림 종류가 틀렸어요")
    t = spec["cover"]["title"]
    for l in (t if isinstance(t, list) else [t]):
        if len(l) > 7:
            bad.append(f"1장 제목은 한 줄 7자 이내: {l}")
    return bad


def build(spec_path: str, reel: bool = False) -> list[str]:
    spec = json.load(open(spec_path, encoding="utf-8"))
    bad = check(spec)
    if bad:
        raise SystemExit("고칠 것:\n- " + "\n- ".join(bad))
    out = os.path.dirname(os.path.abspath(spec_path))
    n = len(spec["slides"]) + 2
    pages = [cover(spec, n)] + [body(sl, i, n) for i, sl in enumerate(spec["slides"], 2)] + [outro(spec, n)]
    paths = []
    for i, p in enumerate(pages, 1):
        f = os.path.join(out, f"{i:02d}.jpg")
        p.save(f, quality=93, subsampling=0)
        paths.append(f)
    if reel:
        make_reel(paths, os.path.join(out, "reel.mp4"), spec.get("mood", "calm"), spec_path)
    return paths


def make_reel(paths, out, mood, seed):
    """카드를 한 장씩 넘기는 세로 영상(1080x1920, 위아래 흰 여백). 첫 장 2.2초, 나머지 2.8초."""
    import shutil, tempfile
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = tempfile.mkdtemp()
    lst = os.path.join(tmp, "list.txt")
    total = 0.0
    with open(lst, "w") as fh:
        for i, p in enumerate(paths):
            tall = Image.new("RGB", (1080, 1920), "white")
            tall.paste(Image.open(p), (0, (1920 - H) // 2))
            q = os.path.join(tmp, f"{i:02d}.png")
            tall.save(q)
            d = 2.2 if i == 0 else 2.8
            total += d
            fh.write(f"file '{q}'\nduration {d}\n")
        fh.write(f"file '{q}'\n")
    tracks = sorted(glob.glob(os.path.join(ROOT, "assets", "music", mood, "*.m4a")))
    if tracks:
        pick = tracks[int(hashlib.md5(os.path.basename(os.path.dirname(os.path.abspath(seed))).encode()).hexdigest(), 16) % len(tracks)]
        audio = ["-stream_loop", "-1", "-t", f"{total:.1f}", "-i", pick]
    else:
        audio = ["-f", "lavfi", "-t", f"{total:.1f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, *audio,
                    "-filter_complex", f"[0:v]fps=30,format=yuv420p[v];[1:a]afade=t=out:st={total - 1.5:.1f}:d=1.5[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.1f}", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in build(sys.argv[1], reel="--reel" in sys.argv):
        print(p)
