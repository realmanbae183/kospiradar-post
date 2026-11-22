import sys, os, json
sys.path.insert(0, 'tools')
from PIL import Image, ImageDraw
from chartset import F, W, H, M, INK, SUB, MUTE, RULE, RED, BLUE, fitf, write, black_head
import breaking
D = os.path.dirname(os.path.abspath(__file__))

def numbered(head, items, img=None, foot=None):
    c = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(c)
    y = black_head(c, d, head) + 50
    if img:
        im = Image.open(img).convert("RGB")
        bw = W - 2 * 40; bh = round(im.height * bw / im.width)
        c.paste(im.resize((bw, bh), Image.LANCZOS), (40, y)); y += bh + 40
    room = H - 70 - y
    n = len(items); step = room / n
    fn = F("Black", 64)
    fa, sa = fitf(d, [i[0] for i in items], "Black", 62, W - 2 * M - 90)
    fb, sb = fitf(d, [i[1] for i in items], "Bold", 44, W - 2 * M - 90)
    blk = sa + 22 + sb
    for k, (a, b) in enumerate(items):
        yy = y + step * k + (step - blk) / 2
        d.text((M, yy - 4), f"{k+1}.", font=fn, fill=INK)
        write(d, M + 90, yy, a, fa)
        write(d, M + 90, yy + sa + 22, b, fb, base=SUB)
        if k < n - 1:
            d.line((M, y + step * (k + 1), W - M, y + step * (k + 1)), fill=RULE, width=2)
    return c

b = breaking.Breaking(os.path.join(D, 'spec.json'))
b.check = None
c2 = numbered(["F4가 정한 것,", "딱 세 가지"], [
    ("불법 공매도 3개월 집중 감시", "공매도 금지는 {b:아님}, 불법만 잡는다"),
    ("자사주 하루 매수한도 완화", "{r:24일부터 3개월}간"),
    ("증안펀드 가동 준비 착수", "새로 만드는 거 아님, 시점·규모 {b:미정}")])
c3 = numbered(["과거 증안펀드,", "들어오면 올랐다"], [
    ("2003·2008년 투입 후", "코스피 약 {r:40% 상승} (키움 한지영 분석)"),
    ("2020년 조성 발표", "바로 다음 날 코스피 {r:8% 넘게 급등}"),
    ("2022·2024년", "집행 없이도 {r:발표 전후로 바닥}")], img=os.path.join(D, 'zungan.jpg'))
cards = [b.cover(), c2, c3, b.outro({"lines": ["증안펀드", "진짜 들어올까?"], "char": "bd12_돋보기"})]
b.sp["cards"] = []
# reuse build's reel code by monkeypatching card list
import types
def build2(self):
    import tempfile, subprocess
    from chartset import RW, RH
    for f in os.listdir(D):
        if f.startswith('c0') and f.endswith('.jpg'): os.remove(os.path.join(D, f))
    for i, im in enumerate(cards, 1): im.save(os.path.join(D, f"c{i:02d}.jpg"), quality=93)
    frames = [self.reel_cover()]
    for im in cards[1:]:
        t = Image.new("RGB", (RW, RH), "white"); t.paste(im, (0, (RH - H) // 2)); frames.append(t)
    durs = [2.6] + [3.6] * (len(frames) - 2) + [2.4]
    tmp = tempfile.mkdtemp(); lst = os.path.join(tmp, "l.txt")
    with open(lst, "w") as fh:
        for i, (f, du) in enumerate(zip(frames, durs)):
            p = os.path.join(tmp, f"{i:02d}.png"); f.save(p); fh.write(f"file '{p}'\nduration {du}\n")
        fh.write(f"file '{p}'\n")
    total = sum(durs)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",lst,"-i",self.p(self.sp["music"]),
        "-filter_complex",f"[0:v]fps=30,format=yuv420p[v];[1:a]atrim=0:{total},afade=t=out:st={total-1.5}:d=1.5[a]",
        "-map","[v]","-map","[a]","-t",f"{total}","-c:v","libx264","-preset","veryfast","-crf","18","-c:a","aac","-b:a","160k",
        "-movflags","+faststart",os.path.join(D,"reel.mp4")],check=True)
    sh = Image.new("RGB", (4*324+50, 405+20), "#EDEDED")
    for i, im in enumerate(cards): sh.paste(im.resize((324, 405)), (10 + i*334, 10))
    sh.save('/tmp/sheet2.jpg')
build2(b)
