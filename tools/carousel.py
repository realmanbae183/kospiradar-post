"""tools/carousel.py — 폴더의 c01.jpg~c10.jpg 를 인스타 여러 장 게시물(캐러셀)로 올린다.
  python tools/carousel.py <폴더> <캡션 파일> [test]
사진은 저장소 공개 주소(raw.githubusercontent.com)로 넘겨서 인스타가 직접 가져가게 한다. test 면 게시 직전까지만.
"""
import glob, os, sys, time, urllib.parse, requests

IG_USER = os.environ.get("IG_USER") or "17841441575106165"
API = "https://graph.facebook.com/v26.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "realmanbae183/kospiradar-post")
SHA = os.environ.get("GITHUB_SHA", "main")


def wait(cid, tok):
    for _ in range(60):
        s = requests.get(f"{API}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if s.get("status_code") in ("FINISHED", None):
            return
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"[인스타] 처리 실패: {s}")
        time.sleep(3)
    raise SystemExit("[인스타] 처리 시간 초과")


def main(folder, cap_file, test):
    tok = os.environ["IG_TOKEN"]
    files = sorted(glob.glob(os.path.join(folder, "c[0-9][0-9].jpg")))[:10]
    if len(files) < 2:
        raise SystemExit(f"[인스타] 사진이 2장 미만: {folder}")
    kids = []
    for f in files:
        url = f"https://raw.githubusercontent.com/{REPO}/{SHA}/" + urllib.parse.quote(f)
        r = requests.post(f"{API}/{IG_USER}/media", data={"image_url": url, "is_carousel_item": "true",
                                                          "access_token": tok}, timeout=60)
        if not r.ok:
            raise SystemExit(f"[인스타] 사진 올리기 실패 {f}: {r.status_code} {r.text[:300]}")
        kids.append(r.json()["id"])
    for k in kids:
        wait(k, tok)
    cap = open(cap_file, encoding="utf-8").read().strip()[:2150]
    r = requests.post(f"{API}/{IG_USER}/media", data={"media_type": "CAROUSEL", "children": ",".join(kids),
                                                      "caption": cap, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"[인스타] 묶음 만들기 실패: {r.status_code} {r.text[:300]}")
    cid = r.json()["id"]
    wait(cid, tok)
    if test:
        print(f"[인스타] 시험 통과 — 사진 {len(kids)}장 묶음 OK, 게시는 안 함")
        return
    for _ in range(12):                       # "아직 준비 안 됨"(9007)이면 잠깐 기다렸다 다시
        p = requests.post(f"{API}/{IG_USER}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
        if p.ok or "9007" not in p.text:
            break
        time.sleep(10)
    if not p.ok:
        raise SystemExit(f"[인스타] 게시 실패: {p.status_code} {p.text[:300]}")
    print(f"[인스타] 카드뉴스 {len(kids)}장 게시 완료:", p.json().get("id"))


if __name__ == "__main__":
    try:
        main(sys.argv[1], sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == "test")
    except BaseException as e:
        print("::error title=carousel::" + str(e).replace("\n", "%0A")[:2000])
        raise
