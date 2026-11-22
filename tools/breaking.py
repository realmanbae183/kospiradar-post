"""버거대왕 속보(BREAKING) 세트 생성기 — 카드뉴스 여러 장 + 릴스 1개.

  python3 tools/breaking.py <spec.json>   → spec 폴더에 c01~cNN.jpg, reel.mp4 (+ 임시 폴더에 sheet.jpg)

올리기는 chartpost.yml (dir=그 폴더, 둘 다, 지금 올리기).
규칙 (2026-11-23 지훈 님):
  - 사진은 지훈 님이 보낸 것만 쓴다(웹에서 유명인 보도사진을 내려받지 않음). 없으면 버거대왕(bd23_속보).
  - 부인·반박이 있으면 표지와 본문에 같이 넣고 출처를 단다. 확인 안 된 건 "보도"로만.
  - 글자는 기본 검정, 좋은 신호만 {r:..}, 나쁜 신호만 {b:..}.
  - 음악은 assets/music/breaking/ 의 급박한 곡.

spec.json:
  {"photo": "cover.jpg", "tag": "BREAKING", "source": "디인포메이션 보도",
   "title": ["두 줄 제목", "..."], "sub": "표지 아래 한 줄(부인 포함)",
   "music": "../../assets/music/breaking/breaking1.mp3",
   "cards": [ {"type": "text", "head": [..], "lines": [..], "char": "bd12_돋보기"},
              {"type": "big", "head": [..], "rows": [["라벨", 값, "표시 글", "red|blue|ink"], ..], "note": ".."},
              {"type": "quote", "head": [..], "who": "..", "quote": [..], "note": ".."},
              {"type": "check", "head": [..], "rows": [["항목", "판정", "red|blue|grey"], ..], "foot": ".."},
              {"type": "outro", "lines": [..], "char": "bd25_팔로우부탁"} ]}
"""
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from chartset import (F, W, H, RW, RH, M, INK, SUB, MUTE, RULE, RED, BLUE,  # noqa: E402
                      fitf, write, paste_img, black_head, white_head, tw)
from cardnews import character  # noqa: E402

COL = {"red": RED, "blue": BLUE, "ink": INK, "grey": MUTE}


def tag_bar(d, y, text="BREAKING", dark=False):
    f = F("Black", 44)
    w = d.textlength(text, font=f) + 56
    d.rectangle((M, y, M + w, y + 76), fill=RED)
    d.text((M + 28, y + 12), text, font=f, fill="white")
    return M + w


class Breaking:
    def __init__(self, spec_path):
        self.sp = json.load(open(spec_path, encoding="utf-8"))
        self.dir = os.path.dirname(os.path.abspath(spec_path))

    def p(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    # 표지
    def cover(self):
        sp = self.sp
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        x = tag_bar(d, 70, sp.get("tag", "BREAKING"))
        d.text((x + 24, 84), sp.get("source", ""), font=F("Bold", 40), fill=SUB)
        f, s = fitf(d, sp["title"], "Black", 110, W - 2 * M)
        y = 190
        for l in sp["title"]:
            write(d, M, y, l, f); y += int(s * 1.2)
        y += 10
        if sp.get("sub"):
            f2, _ = fitf(d, [sp["sub"]], "Bold", 44, W - 2 * M)
            write(d, M, y, sp["sub"], f2, base=SUB); y += 80
        box = (M - 28, y + 10, W - M + 28, H - 70)
        if sp.get("photo"):
            paste_img(c, self.p(sp["photo"]), box, radius=36, border=None)
            d.text((box[0] + 22, box[3] - 48), "자료사진", font=F("Medium", 26), fill="white")
        else:
            d.rounded_rectangle(box, radius=36, fill="#F2F3F5")
            im = character("bd23_속보", int((box[3] - box[1]) * 0.9), cut_bg=True)
            c.paste(im, ((W - im.width) // 2, box[3] - im.height), im)
        d.text((M, H - 52), "@stock_burger_king", font=F("Bold", 28), fill=MUTE)
        return c

    def reel_cover(self):
        sp = self.sp
        if sp.get("photo"):
            c = Image.new("RGB", (RW, RH), "black")
            im = Image.open(self.p(sp["photo"])).convert("RGB")
            if im.width / im.height > 0.75:                 # 가로 사진: 폭에 맞춰 아래쪽에
                im = im.resize((RW, round(im.height * RW / im.width)), Image.LANCZOS)
                c.paste(im, (0, RH - im.height - 180))
                d = ImageDraw.Draw(c)
                tag_bar(d, 260, sp.get("tag", "BREAKING"))
                f, s = fitf(d, sp["title"], "Black", 124, RW - 2 * M)
                y = 380
                for l in sp["title"]:
                    write(d, M, y, l, f, base="#FFFFFF", dark=True); y += int(s * 1.2)
                if sp.get("sub"):
                    f2, _ = fitf(d, [sp["sub"]], "Bold", 50, RW - 2 * M)
                    write(d, M, y + 24, sp["sub"], f2, base="#D9D9D9", dark=True)
                d.text((M, RH - 120), sp.get("source", ""), font=F("Bold", 38), fill="#BDBDBD")
                return c
            r = max(RW / im.width, RH / im.height)
            im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
            l = (im.width - RW) // 2
            c.paste(im.crop((l, 0, l + RW, RH)), (0, 0))
            g = Image.new("L", (1, RH))
            for y in range(RH):
                g.putpixel((0, y), 225 if y < 820 else int(max(60, 225 - (y - 820) * 0.5)))
            c = Image.composite(Image.new("RGB", (RW, RH), "black"), c, g.resize((RW, RH)))
            base = "#FFFFFF"
        else:
            c = Image.new("RGB", (RW, RH), "#F2F3F5")
            im = character("bd23_속보", 1000, cut_bg=True)
            c.paste(im, ((RW - im.width) // 2, RH - im.height - 120), im)
            base = INK
        d = ImageDraw.Draw(c)
        tag_bar(d, 200, sp.get("tag", "BREAKING"))
        f, s = fitf(d, sp["title"], "Black", 120, RW - 2 * M)
        y = 320
        for l in sp["title"]:
            write(d, M, y, l, f, base=base, dark=True); y += int(s * 1.2)
        if sp.get("sub"):
            f2, _ = fitf(d, [sp["sub"]], "Bold", 48, RW - 2 * M)
            write(d, M, y + 20, sp["sub"], f2, base="#D9D9D9" if base != INK else SUB, dark=True)
        return c

    def text(self, cd):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = black_head(c, d, cd["head"], cd.get("char"))
        f, s = fitf(d, cd["lines"], "Bold", 76, W - 2 * M)
        hgt = sum(int(s * 0.7) if l == "" else int(s * 1.55) for l in cd["lines"])
        y = max(top + 90, top + (H - 60 - top - hgt) // 2)
        for l in cd["lines"]:
            if l == "":
                y += int(s * 0.7); continue
            write(d, M, y, l, f); y += int(s * 1.55)
        return c

    def big(self, cd):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        y = white_head(d, cd["head"]) + 80
        mx = max(r[1] for r in cd["rows"])
        for lab, v, show, col in cd["rows"]:
            d.text((M, y), lab, font=F("Bold", 44), fill=SUB)
            y += 70
            bw = int((W - 2 * M) * v / mx)
            d.rounded_rectangle((M, y, M + bw, y + 110), radius=18, fill=COL.get(col, INK))
            f, _ = fitf(d, [show], "Black", 76, W - 2 * M - 40)
            tx = M + 30 if bw > tw(d, show, f) + 60 else M + bw + 24
            fill = "white" if bw > tw(d, show, f) + 60 else COL.get(col, INK)
            d.text((tx, y + 16), show, font=f, fill=fill)
            y += 180
        if cd.get("note"):
            f, s = fitf(d, cd["note"], "Black", 70, W - 2 * M)
            for l in cd["note"]:
                write(d, M, y, l, f); y += int(s * 1.3)
        return c

    def quote(self, cd):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        top = black_head(c, d, cd["head"], cd.get("char"))
        fq, sq = fitf(d, cd["quote"], "Black", 92, W - 2 * M - 20)
        hgt = 120 + len(cd["quote"]) * int(sq * 1.35) + 100 + (len(cd.get("note", [])) * 80 + 150 if cd.get("note") else 0)
        y = max(top + 90, top + (H - 60 - top - hgt) // 2)
        d.text((M, y - 40), "“", font=F("Black", 220), fill=RULE)
        y += 120
        f, s = fq, sq
        for l in cd["quote"]:
            write(d, M + 10, y, l, f); y += int(s * 1.35)
        y += 30
        d.line((M, y, M + 120, y), fill=INK, width=4)
        d.text((M, y + 26), cd["who"], font=F("Bold", 42), fill=SUB)
        if cd.get("note"):
            y += 150
            f, s = fitf(d, cd["note"], "Bold", 56, W - 2 * M)
            for l in cd["note"]:
                write(d, M, y, l, f); y += int(s * 1.5)
        return c

    def check(self, cd):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        y = white_head(d, cd["head"]) + 50
        for lab, ver, col in cd["rows"]:
            d.text((M, y + 34), lab, font=F("Bold", 50), fill=INK)
            f = F("Black", 50)
            d.text((W - M - d.textlength(ver, font=f), y + 34), ver, font=f, fill=COL.get(col, INK))
            y += 132
            d.line((M, y, W - M, y), fill=RULE, width=2)
        if cd.get("foot"):
            y += 60
            f, s = fitf(d, cd["foot"], "Black", 76, W - 2 * M)
            for l in cd["foot"]:
                write(d, M, y, l, f); y += int(s * 1.3)
        return c

    def outro(self, cd):
        c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
        f, s = fitf(d, cd["lines"], "Black", 130, W - 120)
        for k, l in enumerate(cd["lines"]):
            write(d, W / 2, 90 + k * int(s * 1.2), l, f, align="center")
        write(d, W / 2, 110 + len(cd["lines"]) * int(s * 1.2), "팔로우하고 돌발 뉴스 정리 받아보기", F("Bold", 42), align="center", base=SUB)
        im = character(cd.get("char", "bd25_팔로우부탁"), 680, cut_bg=True)
        c.paste(im, ((W - im.width) // 2, H - im.height - 90), im)
        t = cd.get("disc", "보도 내용 정리이며 매수·매도 권유가 아닙니다. 투자 판단과 책임은 본인에게 있습니다.")
        ff = F("Regular", 22)
        d.text(((W - d.textlength(t, font=ff)) / 2, H - 52), t, font=ff, fill=MUTE)
        return c

    def build(self):
        cards = [self.cover()] + [getattr(self, cd["type"])(cd) for cd in self.sp["cards"]]
        cards = cards[:10]
        for i, im in enumerate(cards, 1):
            im.save(os.path.join(self.dir, f"c{i:02d}.jpg"), quality=93)
        frames = [self.reel_cover()]
        for im in cards[1:]:
            t = Image.new("RGB", (RW, RH), "white")
            t.paste(im, (0, (RH - H) // 2))
            frames.append(t)
        durs = [2.6] + [3.0] * (len(frames) - 2) + [2.4]
        tmp = tempfile.mkdtemp()
        lst = os.path.join(tmp, "l.txt")
        with open(lst, "w") as fh:
            for i, (f, du) in enumerate(zip(frames, durs)):
                p = os.path.join(tmp, f"{i:02d}.png"); f.save(p)
                fh.write(f"file '{p}'\nduration {du}\n")
            fh.write(f"file '{p}'\n")
        total = sum(durs)
        music = self.p(self.sp["music"])
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", music,
                        "-filter_complex", f"[0:v]fps=30,format=yuv420p[v];[1:a]atrim=0:{total},afade=t=out:st={total - 1.5}:d=1.5[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{total}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.join(self.dir, "reel.mp4")], check=True)
        s = 0.3; cw, ch = int(W * s), int(H * s)
        n = len(cards); cols = 5; rows = (n + cols - 1) // cols
        sh = Image.new("RGB", (cw * cols + 60, ch * rows + 10 * (rows + 1)), "#EDEDED")
        for i, im in enumerate(cards):
            sh.paste(im.resize((cw, ch), Image.LANCZOS), (10 + (i % cols) * (cw + 10), 10 + (i // cols) * (ch + 10)))
        sh.save(os.path.join(tmp, "sheet.jpg"), quality=85)
        frames[0].resize((540, 960)).save(os.path.join(tmp, "reel_cover.jpg"))
        print(tmp)


if __name__ == "__main__":
    Breaking(sys.argv[1]).build()
