"""
insta.py — 오늘의 국장 그림을 릴스 영상과 사진 게시물로 인스타그램(@stock_burger_king)에 올린다.
  python insta.py photo <공개 jpg 주소> media/날짜-kr.json   사진 게시물 올리기
  python insta.py video state/brief/kr.png out.mp4      그림 → 9:16 릴스 영상 (8초, 천천히 확대, 무음)
  python insta.py post  out.mp4 state/brief/kr.json      릴스 올리기 (IG_TOKEN 필요)
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

CAPTION = """[{date}]
오늘의 국장 지표입니다.🍔

매일 장 마감 후 오늘의 국장 지표를 정리해 업로드하고 있습니다.

다음 날 새로운 국장 지표가 업로드되면
피드의 통일성과 깔끔한 구성을 위해 이전 영상은 보관처리하고 있습니다.

매일 업데이트되는 시장 흐름이 궁금하시다면
팔로우하시고 편하게 정보 받아가세요~❤️


#투자 #주식 #경제 #경제적자유 #코스피"""


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


def caption(brief: str) -> str:
    b = json.load(open(brief, encoding="utf-8"))
    date = f"{b.get('date') or ''} ({b.get('dow') or ''})".strip()
    return CAPTION.format(date=date)


def post(mp4: str, brief: str, publish: bool = True) -> str:
    tok = os.environ["IG_TOKEN"]
    cap = caption(brief)
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


def photo(url: str, brief: str) -> str:
    """사진 게시물. 인스타는 사진을 '공개 주소'로만 받아 가서, 이 공개 저장소에 올린 jpg 주소를 넘긴다."""
    tok = os.environ["IG_TOKEN"]
    r = requests.post(f"{API}/{IG_USER}/media", data={"image_url": url, "caption": caption(brief), "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"[인스타] 사진 컨테이너 실패: {r.status_code} {r.text[:400]}")
    cid = r.json()["id"]
    for _ in range(24):
        s = requests.get(f"{API}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"[인스타] 사진 처리 실패: {s}")
        time.sleep(5)
    p = requests.post(f"{API}/{IG_USER}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not p.ok:
        raise SystemExit(f"[인스타] 사진 게시 실패: {p.status_code} {p.text[:300]}")
    print("[인스타] 사진 게시 완료:", p.json().get("id"))
    return p.json().get("id")


def main(argv: list[str]) -> None:
    if argv[1] == "video":
        video(argv[2], argv[3])
    elif argv[1] == "post":
        post(argv[2], argv[3])
    elif argv[1] == "test":
        post(argv[2], argv[3], publish=False)
    elif argv[1] == "photo":
        photo(argv[2], argv[3])
    elif argv[1] == "caption":
        print(caption(argv[2]))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except BaseException as e:      # GitHub 화면에 이유가 보이게
        print("::error title=insta::" + str(e).replace("\n", "%0A")[:2000])
        raise
