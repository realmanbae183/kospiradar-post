"""
insta.py — 굿모닝 미장 · 오늘의 국장 그림을 인스타그램(@stock_burger_king)에 릴스 1개 + 스토리 1개로 올린다.
  python insta.py video media/날짜-kr.png out.mp4           그림 → 9:16 릴스 영상 (8초, 고정 화면, 무음)
  python insta.py frame out.mp4 out.jpg                      영상 한 장면 → 스토리용 9:16 jpg
  python insta.py post  out.mp4 media/날짜-kr.json [캡션파일] 릴스 올리기
  python insta.py story <공개 jpg 주소>                       스토리 올리기
  python insta.py caption media/날짜-kr.json [캡션파일]       캡션 미리보기
캡션은 매일 Claude 가 쓴 posts/날짜-kind.ig.txt 를 쓰고, 없으면 아래 기본 틀로 만든다.
열쇠(IG_TOKEN)는 GitHub Secrets 에만 있다. 페이지 토큰이라 만료가 없다(단, 90일마다 데이터 접근 갱신 필요할 수 있음).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import requests

IG_USER = "17841441575106165"          # @stock_burger_king (공개 정보)
API = "https://graph.facebook.com/v26.0"

WEEK = "월화수목금토일"
KEEP = "📌 피드를 깔끔하게 보시도록 지난 지표는 다음 날 보관하고, 매일 그날의 새 지표로 찾아옵니다."
TAGS = {"kr": "#투자 #주식 #경제 #경제적자유 #코스피 #코스닥 #국내증시",
        "us": "#투자 #주식 #경제 #미국주식 #미국증시 #나스닥 #SP500"}


def _sgn(p) -> str:
    return "–" if p is None else f"{p:+.2f}%"


def default_caption(b: dict) -> str:
    """Claude 가 쓴 캡션이 없을 때 쓰는 기본 틀 (숫자는 재료에서만)."""
    from datetime import date as _d
    if "us" in b:                                   # 굿모닝 미장
        u = b["us"]; y, m, d = map(int, str(b["date"]).split("-"))
        day = f"{m}월 {d}일 {WEEK[_d(y, m, d).weekday()]}요일"
        ix = {x["n"]: x.get("p") for x in u.get("idx", [])}
        up = sum(1 for v in ix.values() if (v or 0) > 0)
        mark = "📈" if up >= 2 else "📉"
        fg = u.get("fg") or {}
        return (f"🍔 [{day}] 굿모닝 미장\n🇺🇸 미국 증시, 오늘은 어떤 흐름이었을까요?\n"
                f"{mark} 다우 {_sgn(ix.get('다우존스'))} · S&P500 {_sgn(ix.get('S&P500'))} · 나스닥 {_sgn(ix.get('나스닥 종합'))}\n"
                + (f"공포탐욕지수는 {fg.get('v')}, '{fg.get('r')}' 구간이에요.\n" if fg.get("v") is not None else "")
                + "매일 아침 미국장 마감 지표를 한 장으로 정리해 올려요. 팔로우하고 아침마다 확인해 보세요 ❤️\n"
                + KEEP + "\n\n" + TAGS["us"])
    t = b.get("today") or b                          # 오늘의 국장
    ix = {x["n"]: x.get("p") for x in t.get("idx", [])}
    dow = (t.get("dow") or b.get("dow") or "").rstrip("요일")
    kp = ix.get("코스피") or 0
    mark, word = ("📈", "상승") if kp > 0 else ("📉", "하락") if kp < 0 else ("➖", "보합")
    return (f"🍔 [{t.get('date') or b.get('date')} {dow}요일] 오늘의 국장\n"
            f"{mark} 코스피 {_sgn(ix.get('코스피'))} · 코스닥 {_sgn(ix.get('코스닥'))}\n"
            f"오늘 국내 증시는 {word} 마감했습니다.\n"
            "업종별 등락부터 투자자 동향, 환율·금·유가까지 오늘의 국장 지표를 한눈에 확인하세요! 📊\n"
            "매일 장 마감 후 업데이트되는 증시 정보, 팔로우하고 꾸준히 확인해 보세요 ❤️\n"
            + KEEP + "\n\n" + TAGS["kr"])


def video(img: str, out: str, sec: int = 8) -> None:
    """정사각 그림을 흐린 배경 위에 가로 꽉 차게 올린 1080x1920 영상.
    글자가 뭉개지지 않게 움직임 없이 고정, 원본(3배 해상도)에서 한 번만 고품질로 줄이고 넉넉한 화질로 굽는다."""
    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:                                 # GitHub 실행기에 ffmpeg 가 없으면 파이썬 패키지에 든 것을 쓴다
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    fc = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=bicubic,crop=1080:1920,boxblur=40:2,eq=brightness=-0.06[bg];"
          "[0:v]scale=1080:-2:flags=lanczos,unsharp=3:3:0.4[fg];"
          "[bg][fg]overlay=x=0:y='(H-h)/2',format=yuv420p[v]")
    cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", str(sec), "-i", img,
           "-f", "lavfi", "-t", str(sec), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-tune", "stillimage", "-crf", "14",
           "-maxrate", "12M", "-bufsize", "24M", "-g", "30", "-r", "30",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def caption(brief: str, cap_file: str | None = None) -> str:
    if cap_file and os.path.exists(cap_file):
        t = open(cap_file, encoding="utf-8").read().strip()
        if t:
            return t[:2150]
    return default_caption(json.load(open(brief, encoding="utf-8")))[:2150]


def frame(mp4: str, out: str) -> None:
    """릴스 영상의 한 장면을 스토리용 jpg 로."""
    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", mp4, "-frames:v", "1", "-q:v", "2", out], check=True)


def story(url: str) -> str:
    """스토리 (사진). 인스타는 '공개 주소'의 jpg 만 받아 간다."""
    tok = os.environ["IG_TOKEN"]
    r = requests.post(f"{API}/{IG_USER}/media", data={"media_type": "STORIES", "image_url": url, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"[인스타] 스토리 컨테이너 실패: {r.status_code} {r.text[:400]}")
    cid = r.json()["id"]
    for _ in range(24):
        st = requests.get(f"{API}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"[인스타] 스토리 처리 실패: {st}")
        time.sleep(5)
    p = requests.post(f"{API}/{IG_USER}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not p.ok:
        raise SystemExit(f"[인스타] 스토리 게시 실패: {p.status_code} {p.text[:300]}")
    print("[인스타] 스토리 게시 완료:", p.json().get("id"))
    return p.json().get("id")


def post(mp4: str, brief: str, publish: bool = True, cap_file: str | None = None) -> str:
    tok = os.environ["IG_TOKEN"]
    cap = caption(brief, cap_file)
    r = requests.post(f"{API}/{IG_USER}/media", data={"media_type": "REELS", "upload_type": "resumable",
                                                      "caption": cap, "share_to_feed": "true", "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"[인스타] 컨테이너 만들기 실패: {r.status_code} {r.text[:400]}")
    cid = r.json()["id"]
    size = os.path.getsize(mp4)
    with open(mp4, "rb") as f:
        u = requests.post(f"https://rupload.facebook.com/ig-api-upload/v26.0/{cid}",
                          headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=f, timeout=300)
    if not u.ok:
        raise SystemExit(f"[인스타] 영상 올리기 실패: {u.status_code} {u.text[:300]}")
    for _ in range(60):                       # 인스타가 영상을 처리할 때까지 (최대 약 5분)
        s = requests.get(f"{API}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"[인스타] 처리 실패: {s}")
        time.sleep(5)
    else:
        raise SystemExit("[인스타] 처리 시간 초과")
    if not publish:                          # 시험: 올리기·처리까지만 확인하고 게시는 안 함 (24시간 뒤 자동 삭제)
        print("[인스타] 시험 통과 — 영상 업로드·처리 OK, 게시는 안 함")
        return cid
    p = requests.post(f"{API}/{IG_USER}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not p.ok:
        raise SystemExit(f"[인스타] 게시 실패: {p.status_code} {p.text[:300]}")
    mid = p.json().get("id")
    print("[인스타] 릴스 게시 완료:", mid)
    return mid


def main(argv: list[str]) -> None:
    cmd, rest = argv[1], argv[2:]
    if cmd == "video":
        video(rest[0], rest[1])
    elif cmd == "frame":
        frame(rest[0], rest[1])
    elif cmd == "post":
        post(rest[0], rest[1], cap_file=rest[2] if len(rest) > 2 else None)
    elif cmd == "test":
        post(rest[0], rest[1], publish=False, cap_file=rest[2] if len(rest) > 2 else None)
    elif cmd == "story":
        story(rest[0])
    elif cmd == "caption":
        print(caption(rest[0], rest[1] if len(rest) > 1 else None))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except BaseException as e:      # GitHub 화면에 이유가 보이게
        print("::error title=insta::" + str(e).replace("\n", "%0A")[:2000])
        raise
