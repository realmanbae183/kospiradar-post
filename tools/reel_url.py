"""tools/reel_url.py — 저장소에 있는 영상을 공개 주소(raw.githubusercontent.com)로 인스타에 넘겨 릴스로 올린다.
  python tools/reel_url.py <저장소 안 영상 경로> <캡션 파일> [test]
긴 영상(30초 넘는 것)은 직접 업로드(rupload)가 거절돼서, 인스타가 주소에서 직접 가져가게 한다.
"""
import os, sys, time, urllib.parse, requests

IG_USER = os.environ.get("IG_USER") or "17841441575106165"
API = "https://graph.facebook.com/v26.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "realmanbae183/kospiradar-post")
SHA = os.environ.get("GITHUB_SHA", "main")


def main(path: str, cap_file: str, test: bool) -> None:
    tok = os.environ["IG_TOKEN"]
    url = f"https://raw.githubusercontent.com/{REPO}/{SHA}/" + urllib.parse.quote(path)
    cap = open(cap_file, encoding="utf-8").read().strip()[:2150]
    r = requests.post(f"{API}/{IG_USER}/media", data={"media_type": "REELS", "video_url": url, "caption": cap,
                                                      "share_to_feed": "true", "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"[인스타] 컨테이너 만들기 실패: {r.status_code} {r.text[:400]}")
    cid = r.json()["id"]
    for _ in range(120):                      # 인스타가 영상을 가져가 처리할 때까지 (최대 약 10분)
        s = requests.get(f"{API}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"[인스타] 처리 실패: {s}")
        time.sleep(5)
    else:
        raise SystemExit("[인스타] 처리 시간 초과")
    if test:
        print("[인스타] 시험 통과 — 영상 업로드·처리 OK, 게시는 안 함")
        return
    p = requests.post(f"{API}/{IG_USER}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not p.ok:
        raise SystemExit(f"[인스타] 게시 실패: {p.status_code} {p.text[:300]}")
    print("[인스타] 릴스 게시 완료:", p.json().get("id"))


if __name__ == "__main__":
    try:
        main(sys.argv[1], sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == "test")
    except BaseException as e:
        print("::error title=reel_url::" + str(e).replace("\n", "%0A")[:2000])
        raise
