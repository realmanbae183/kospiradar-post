"""버거대왕 차트 세트 생성기 — 종목 하나의 카드뉴스 8장 + 릴스 1개.

  python3 tools/chartset.py <spec.json>     → spec 폴더에 c01~c08.jpg, reel.mp4

틀 (2026-11-22 지훈 님 확정):
  c01 표지 A안 (큰 제목 + 큰 질문 한 줄 + 사진)      릴스 첫 장은 B안 (사진 꽉 + 흰 글씨)
  c02 목차 (블랙 헤더 "넘기면 나오는 네 가지")
  c03 오늘 무슨 일 (블랙 헤더 + 캔들 하나)
  c04 어제 예상 채점 (흰 바탕 + 점검 차트)
  c05 지금 위치 (블랙 헤더 + 가로 한 줄: 2차 지지 · 1차 지지 · 지금 · 1차 저항 · 2차 저항)
  c06 보조지표 (흰 바탕 + 한 줄씩 판정)
  c07 내일 차트 (차트 크게 + 지지·저항 두 줄)
  c08 마무리 (버거대왕 + 면책)
spec.json 은 cards/2026-11-20-samsung-set/spec.json 을 본보기로 쓴다.
  prev_day = 직전 거래일 이름("어제", 월요일엔 "금요일"), next = 다음 거래일 이름("내일", 금요일엔 "월요일")
  photo 가 없으면 cover_char(버거대왕)로 표지를 채운다. music = ../../assets/music/chart/<종목>.mp3
색: 기본 검정, 좋은 신호 빨강 {r:..}, 나쁜 신호 파랑 {b:..}. 작은 설명 글씨는 넣지 않는다.
"""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from cardnews import character  # noqa: E402

W, H, RW, RH = 1080, 1350, 1080, 1920
FD = os.path.join(ROOT, "assets", "fonts", "pretendard")
INK, SUB, MUTE, RULE = "#111111", "#6B6B6B", "#A3A3A3", "#E6E6E6"
RED, BLUE, DRED, DBLUE = "#E5383B", "#2F6FED", "#FF6B6E", "#7AA2FF"
M = 88


def F(w, s):
    return ImageFont.truetype(os.path.join(FD, f"Pretendard-{w}.otf"), s)


def spans(txt, base=INK, dark=False):
    out = []
    for m in re.finditer(r"\{([br]):([^}]*)\}|([^{]+)", txt):
        if m.group(1):
            out.append((m.group(2), (DBLUE if dark else BLUE) if m.group(1) == "b" else (DRED if dark else RED)))
        else:
            out.append((m.group(3), base))
    return out


def tw(d, txt, f):
    return sum(d.textlength(p, font=f) for p, _ in spans(txt))


def fitf(d, lines, w, size, maxw):
    while size > 40 and max(tw(d, l, F(w, size)) for l in lines) > maxw:
        size -= 4
    return F(w, size), size


def write(d, x, y, txt, f, base=INK, align="left", dark=False):
    parts = spans(txt, base, dark)
    if align == "center":
        x -= sum(d.textlength(p, font=f) for p, _ in parts) / 2
    for p, c in parts:
        d.text((x, y), p, font=f, fill=c)
        x += d.textlength(p, font=f)


def num(p):
    return f"{p:,.0f}"


def paste_img(c, path, box, radius=28, crop=None, crop_top=0.0, border=RULE):
    x0, y0, x1, y1 = [int(v) for v in box]
    im = Image.open(path).convert("RGB")
    im = im.crop(crop or (0, int(im.height * crop_top), im.width, im.height))
    bw, bh = x1 - x0, y1 - y0
    r = max(bw / im.width, bh / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    l, t = (im.width - bw) // 2, (im.height - bh) // 4
    im = im.crop((l, t, l + bw, t + bh))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, bw - 1, bh - 1), radius=radius, fill=255)
    c.paste(im, (x0, y0), m)
    if border:
        ImageDraw.Draw(c).rounded_rectangle((x0, y0, x1, y1), radius=radius, outline=border, width=2)


def black_head(c, d, head, char=None):
    f, s = fitf(d, head, "Black", 100, W - 2 * M - (170 if char else 0))
    lh = int(s * 1.22)
    HH = 110 + len(head) * lh + 60
    d.rectangle((0, 0, W, HH), fill="#111111")
    for k, l in enumerate(head):
        write(d, M, 110 + k * lh, l, f, base="#FFFFFF", dark=True)
    if char:
        im = character(char, 190, cut_bg=True)
        c.paste(im, (W - im.width - 40, HH - im.height), im)
    return HH


def white_head(d, head):
    f, s = fitf(d, head, "Black", 100, W - 2 * M)
    lh = int(s * 1.22)
    for k, l in enumerate(head):
        write(d, M, 110 + k * lh, l, f)
    y = 110 + len(head) * lh + 40
    d.line((M, y, W - M, y), fill=INK, width=3)
    return y


class Set:
    def __init__(self, spec_path):
        self.sp = json.load(open(spec_path, encoding="utf-8"))
        self.dir = os.path.dirname(os.path.abspath(spec_path))

    def p(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    def cover_photo(self, c, box, radius=40):
        sp = self.sp
        if sp.get("photo"):                         # 사진은 자르거나 확대하지 않고 칸 안에 통째로 맞춤
            x0, y0, x1, y1 = [int(v) for v in box]
            im = Image.open(self.p(sp["photo"])).convert("RGB")
            r = min((x1 - x0) / im.width, (y1 - y0) / im.height)
            im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
            m = Image.new("L", im.size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
            c.paste(im, ((x0 + x1 - im.width) // 2, y0 + (y1 - y0 - im.height) // 2), m)
        else:                                       # 짤이 없으면 버거대왕
            x0, y0, x1, y1 = box
            ImageDraw.Draw(c).rounded_rectangle(box, radius=radius, fill="#F2F3F5")
            im = character(sp.get("cover_char", "bd03_급락멘붕"), int(min(x1 - x0, y1 - y0) * 0.92), cut_bg=True)
            c.paste(im, (int((x0 + x1 - im.width) / 2), int(y1 - im.height)), im)

    # c01 표지 A안
    def c01(self):
        sp = self.sp
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        f, _ = fitf(d, [sp["title"]], "Black", 200, W - 120)
        write(d, W / 2, 50, sp["title"], f, align="center")
        f2, _ = fitf(d, [sp["hook"]], "Black", 84, W - 120)
        write(d, W / 2, 290, sp["hook"], f2, align="center")
        self.cover_photo(c, (60, 430, W - 60, H - 60))
        return c

    # 릴스 첫 장 B안
    def reel_cover(self):
        sp = self.sp
        if sp.get("photo"):
            im = Image.open(self.p(sp["photo"])).convert("RGB")
            # 뒤는 같은 사진을 크게 흐리게 깔고, 사진 본체는 자르거나 확대하지 않고 통째로 맞춤
            r = max(RW / im.width, RH / im.height)
            bg = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
            l, t = (bg.width - RW) // 2, (bg.height - RH) // 2
            bg = bg.crop((l, t, l + RW, t + RH)).filter(ImageFilter.GaussianBlur(40))
            c = Image.composite(Image.new("RGB", (RW, RH), "black"), bg, Image.new("L", (RW, RH), 150))
            top, bot = 640, RH - 120
            r = min(RW / im.width, (bot - top) / im.height)
            im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
            c.paste(im, ((RW - im.width) // 2, top + (bot - top - im.height) // 2))
            dark, base = True, "#FFFFFF"
        else:
            c = Image.new("RGB", (RW, RH), "#F2F3F5")
            im = character(sp.get("cover_char", "bd03_급락멘붕"), 1000, cut_bg=True)
            c.paste(im, ((RW - im.width) // 2, RH - im.height - 120), im)
            dark, base = False, INK
        d = ImageDraw.Draw(c)
        f, _ = fitf(d, [sp["title"]], "Black", 200, RW - 2 * M)
        write(d, M, 260, sp["title"], f, base=base, dark=dark)
        d.text((M, 500), sp.get("reel_sub") or f"{sp['next']} 차트 미리보기", font=F("Black", 76), fill=base)
        return c

    # c02 목차
    def c02(self):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = black_head(c, d, ["넘기면 나오는", "{r:네 가지}"])
        items = [("어제 예상 채점", "review"), ("지금 차트 위치", "pos"), ("보조지표 분석", "ind"), (f"{self.sp['next']} 차트 예상", "tmr")]
        y0 = top + 60
        rh = (H - 80 - y0) / 4
        for i, (t, k) in enumerate(items):
            y = y0 + rh * i
            if i:
                d.line((M, y, W - M, y), fill=RULE, width=2)
            cy = y + rh / 2
            d.text((M, cy - 52), f"{i + 1}", font=F("Black", 64), fill=MUTE)
            d.text((M + 90, cy - 54), t, font=F("Black", 62), fill=INK)
            d.text((M + 92, cy + 22), self.sp["toc"][i], font=F("Medium", 34), fill=SUB)
        return c

    # c03 오늘 무슨 일 (캔들)
    def c03(self):
        sp, t = self.sp, self.sp["today"]
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = black_head(c, d, sp["h_today"])
        ps = [t["high"], t["low"], t["open"], t["close"], sp["prev_close"]]
        lo, hi = min(ps), max(ps)
        pad = (hi - lo) * 0.12
        lo, hi = lo - pad, hi + pad
        y0, y1 = top + 90, H - 110
        Y = lambda p: y0 + (hi - p) / (hi - lo) * (y1 - y0)
        cx = 380
        y = Y(sp["prev_close"])
        for x in range(M, W - M, 26):
            d.line((x, y, min(x + 14, W - M), y), fill=MUTE, width=3)
        d.text((M, y - 44), f"{sp['prev_day']} 종가 {num(sp['prev_close'])}", font=F("Medium", 30), fill=SUB)
        col = BLUE if t["close"] < t["open"] else RED
        d.line((cx, Y(t["high"]), cx, Y(t["low"])), fill=col, width=6)
        d.rectangle((cx - 70, min(Y(t["open"]), Y(t["close"])), cx + 70, max(Y(t["open"]), Y(t["close"])) + 2), fill=col)
        rows = sorted([(t["high"], "고가"), (t["open"], "시가"), (t["close"], "종가"), (t["low"], "저가")], key=lambda r: -r[0])
        ly, last = [], -1e9
        for p, _ in rows:                               # 글자 겹침 방지 (최소 56px 간격)
            yy = max(Y(p), last + 56)
            ly.append(yy); last = yy
        fl, fv = F("Medium", 30), F("Bold", 42)
        for (p, lab), yy in zip(rows, ly):
            d.line((cx + 90, Y(p), cx + 150, yy), fill=RULE, width=2)
            d.text((cx + 170, yy - 20), lab, font=fl, fill=SUB)
            d.text((cx + 250, yy - 28), num(p), font=fv, fill=col if lab in ("종가", "저가" if col == BLUE else "고가") else INK)
        return c

    # c04 어제 예상 채점
    def c04(self):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = white_head(d, ["어제 예상 채점"] + self.sp["h_review"])
        paste_img(c, self.p(self.sp["review_img"]), (M, top + 50, W - M, H - 120), crop=(0, 140, 1080, 950))
        return c

    # c05 지금 위치
    def c05(self):
        sp = self.sp
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = black_head(c, d, sp["h_pos"], char=sp.get("pos_char", "bd11_차트분석"))
        now = sp["today"]["close"]
        s1, s2 = sp["support"]; r1, r2 = sp["resist"]
        lo, hi = s2, r2
        pad = (hi - lo) * 0.07
        lo, hi = lo - pad, hi + pad
        x0, x1 = M + 30, W - M - 30
        X = lambda p: x0 + (p - lo) / (hi - lo) * (x1 - x0)
        ym = top + (H - top) * 0.42
        d.line((x0, ym, x1, ym), fill=RULE, width=8)
        d.line((X(now), ym, X(r2), ym), fill=BLUE, width=8)
        d.line((X(s2), ym, X(now), ym), fill=RED, width=8)
        fn, fl = F("Bold", 44), F("Medium", 30)
        # 두 선이 가까우면 글씨가 겹치지 않게 가운데를 벌린다
        cx = {}
        for a, b in [(r1, r2), (s2, s1)]:
            wa = max(d.textlength(num(a), font=fn), d.textlength("1차 저항", font=fl))
            wb = max(d.textlength(num(b), font=fn), d.textlength("1차 저항", font=fl))
            ca, cb = X(a), X(b)
            gap = (wa + wb) / 2 + 24
            if cb - ca < gap:
                mid = (ca + cb) / 2
                ca, cb = mid - gap / 2, mid + gap / 2
                lo_, hi_ = M - 20 + wa / 2, W - M + 20 - wb / 2
                if ca < lo_: ca, cb = lo_, lo_ + gap
                if cb > hi_: ca, cb = hi_ - gap, hi_
            cx[a], cx[b] = ca, cb
        for p, lab, col, up in [(r2, "2차 저항", BLUE, True), (r1, "1차 저항", BLUE, True),
                                (s1, "1차 지지", RED, False), (s2, "2차 지지", RED, False)]:
            x = X(p)
            d.ellipse((x - 14, ym - 14, x + 14, ym + 14), fill=col)
            x = cx[p]
            s_ = num(p)
            sw = d.textlength(s_, font=fn)
            tx = min(max(x - sw / 2, M - 20), W - M + 20 - sw)
            lw = d.textlength(lab, font=fl)
            lx = min(max(x - lw / 2, M - 20), W - M + 20 - lw)
            if up:
                d.text((tx, ym - 132), s_, font=fn, fill=col)
                d.text((lx, ym - 74), lab, font=fl, fill=SUB)
            else:
                d.text((lx, ym + 36), lab, font=fl, fill=SUB)
                d.text((tx, ym + 76), s_, font=fn, fill=col)
        x = X(now)
        d.ellipse((x - 24, ym - 24, x + 24, ym + 24), fill=INK)
        d.line((x, ym + 24, x, ym + 200), fill=INK, width=3)
        f = F("ExtraBold", 44)
        t = f"지금 {num(now)}"
        tx = min(max(x - d.textlength(t, font=f) / 2, M), W - M - d.textlength(t, font=f))
        d.text((tx, ym + 212), t, font=f, fill=INK)
        return c

    # c06 보조지표
    def c06(self):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = white_head(d, self.sp["h_ind"])
        rows = self.sp["ind"]
        y0, y1 = top + 40, H - 120
        rh = (y1 - y0) / len(rows)
        fv, fj = F("Bold", 50), F("ExtraBold", 44)
        for i, (v, j, col) in enumerate(rows):
            y = y0 + rh * i
            if i:
                d.line((M, y, W - M, y), fill=RULE, width=2)
            cy = y + rh / 2
            d.text((M, cy - 30), v, font=fv, fill=INK)
            d.text((W - M - d.textlength(j, font=fj), cy - 26), j, font=fj,
                   fill={"blue": BLUE, "red": RED, "grey": MUTE}[col])
        return c

    # c07 내일 차트
    def c07(self):
        sp = self.sp
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        paste_img(c, self.p(sp["tomorrow_img"]), (M, 80, W - M, 930), crop_top=0.10)
        lines = [f"{{r:지지}} {num(sp['support'][0])}", f"{{b:저항}} {num(sp['resist'][0])}"]
        f, _ = fitf(d, lines, "Black", 104, W - 2 * M)
        write(d, W / 2, 990, lines[0], f, align="center")
        write(d, W / 2, 1130, lines[1], f, align="center")
        return c

    # c08 마무리
    def c08(self):
        sp = self.sp
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        f, _ = fitf(d, sp["outro"], "Black", 150, W - 120)
        for k, l in enumerate(sp["outro"]):
            write(d, W / 2, 90 + k * 170, l, f, align="center")
        write(d, W / 2, 460, "팔로우하고 매일 장 마감 뒤 받아보기", F("Bold", 42), align="center", base=SUB)
        im = character(sp.get("outro_char", "bd25_팔로우부탁"), 700, cut_bg=True)
        c.paste(im, ((W - im.width) // 2, H - im.height - 90), im)
        t = "개인 기록이며 매수·매도 권유가 아닙니다. 투자 판단과 책임은 본인에게 있습니다."
        ff = F("Regular", 22)
        d.text(((W - d.textlength(t, font=ff)) / 2, H - 52), t, font=ff, fill=MUTE)
        return c

    def build(self, music=None):
        cards = [self.c01(), self.c02(), self.c03(), self.c04(), self.c05(), self.c06(), self.c07(), self.c08()]
        for i, im in enumerate(cards, 1):
            im.save(os.path.join(self.dir, f"c{i:02d}.jpg"), quality=93)
        frames = [self.reel_cover()]
        for im in cards[1:]:
            t = Image.new("RGB", (RW, RH), "white")
            t.paste(im, (0, (RH - H) // 2))
            frames.append(t)
        durs = [2.2, 2.6, 2.6, 3.0, 3.0, 3.0, 3.2, 2.4]
        tmp = tempfile.mkdtemp()
        lst = os.path.join(tmp, "l.txt")
        with open(lst, "w") as fh:
            for i, (f, du) in enumerate(zip(frames, durs)):
                p = os.path.join(tmp, f"{i:02d}.png"); f.save(p)
                fh.write(f"file '{p}'\nduration {du}\n")
            fh.write(f"file '{p}'\n")
        total = sum(durs)
        music = music or self.p(self.sp["music"])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", music,
                        "-filter_complex", f"[0:v]fps=30,format=yuv420p[v];[1:a]atrim=0:{total},afade=t=out:st={total - 1.5}:d=1.5[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{total}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.join(self.dir, "reel.mp4")], check=True)
        # 미리보기 시트
        s = 0.3; cw, ch = int(W * s), int(H * s)
        sh = Image.new("RGB", (cw * 4 + 50, ch * 2 + 30), "#EDEDED")
        for i, im in enumerate(cards):
            sh.paste(im.resize((cw, ch), Image.LANCZOS), (10 + (i % 4) * (cw + 10), 10 + (i // 4) * (ch + 10)))
        sh.save(os.path.join(tmp, "sheet.jpg"), quality=85)
        frames[0].resize((360, 640)).save(os.path.join(tmp, "reel_cover.jpg"))
        print(tmp)


if __name__ == "__main__":
    Set(sys.argv[1]).build()
