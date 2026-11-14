"""
tg_send.py — 텔레그램으로 '사진 → 제목 → 본문' 순서로 보낸다 (키움·블로그에 붙여넣기 쉽게 제목과 본문을 따로).

  python3 tools/tg_send.py post <채팅> <글.md> [사진]       글 하나 (첫 줄 = 제목, 나머지 = 본문)
  python3 tools/tg_send.py seq  <채팅> <name.seq.json> <기준 폴더>   블로그 순서 파일 (제목 → 글·사진 차례대로)

본문은 맨 앞에 빈 줄을 두고 시작한다. 텔레그램은 맨 앞 빈 줄을 지우므로 보이지 않는 문자(U+200B)를 한 줄 붙인다.
토큰: 환경변수 TOK
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

API = "https://api.telegram.org/bot{}/{}"
ZW = "​"


def call(method: str, chat: str, files=None, **data) -> None:
    tok = os.environ["TOK"]
    data["chat_id"] = chat
    for i in range(3):
        r = requests.post(API.format(tok, method), data=data, files=files, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.json().get("parameters", {}).get("retry_after", 3)) + 1)
            continue
        print(method, r.status_code, r.text[:120] if r.status_code != 200 else "")
        break
    time.sleep(1.1)


def text(chat: str, s: str) -> None:
    for i in range(0, len(s), 3900):
        call("sendMessage", chat, text=s[i:i + 3900], disable_web_page_preview="true")


def photo(chat: str, path: str) -> None:
    with open(path, "rb") as fp:
        call("sendPhoto", chat, files={"photo": fp})


def post(chat: str, md: str, img: str | None = None) -> None:
    raw = open(md, encoding="utf-8").read()
    title, _, rest = raw.partition("\n")
    rest = rest.strip("\n")
    if img and os.path.exists(img):
        photo(chat, img)
    if title.strip():
        text(chat, title.strip())
    if rest:
        text(chat, ZW + "\n" + rest)


def seq(chat: str, path: str, base: str) -> None:
    for x in json.load(open(path, encoding="utf-8")):
        if x["type"] == "photo":
            p = os.path.join(base, x["path"])
            if os.path.exists(p):
                photo(chat, p)
        elif x.get("text", "").strip():
            text(chat, x["text"])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "post":
        post(a[1], a[2], a[3] if len(a) > 3 else None)
    elif a and a[0] == "seq":
        seq(a[1], a[2], a[3])
    else:
        print(__doc__)
        sys.exit(1)
