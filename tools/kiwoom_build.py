"""
kiwoom_build.py — 장 마감 뒤 한 번에 도는 오후 작업의 '고정된 부분'을 코드가 만든다.
Claude 는 사람 말투가 필요한 칸(slots.json)만 쓰고, 숫자 목록·동그라미 문장·구분선·면책 줄은 여기서 만든다.

  python3 tools/kiwoom_build.py fetch  <WORK>                 kr-radar 재료와 그림을 WORK 로 받는다 (gh api)
  python3 tools/kiwoom_build.py facts  <WORK>                 WORK/facts.txt (Claude 가 읽을 짧은 요약) + WORK/facts.json
  python3 tools/kiwoom_build.py inbox  <WORK> <blog/_done.json>  수집함 원문 중 아직 안 쓴 것을 WORK/inbox 로 받고 목록 출력
  python3 tools/kiwoom_build.py build  <WORK> <slots.json> <kp 폴더> [kr|kiwoom|notes|all]
        → kp/posts·media (국장 시황), kp/kiwoom/D (종목 세트·레이더·구루·원문 글), WORK/blog2.json (블로그 2편 재료)
        숫자 검사: 칸에 쓴 숫자가 재료에 없으면 '확인 필요'로 출력하고 종료 코드 2 (고치고 다시 build)
  python3 tools/kiwoom_build.py blog   <blocks.json> <출력 폴더>   blog_render 로 블로그 한 편 (title·blocks·tags)

키움 텔레그램 순서 (파일 이름 순서 = 보내는 순서):
  11a-kospi-review(점검) → 11b-kospi(내일 예상) → 12a-samsung-review → 12b-samsung → … → 15b-semco
  → 61~63-sig(과매도) → 70-guru → 801~-note(수집함 원문 글)
각 .md 는 첫 줄 = 제목, 나머지 = 본문. 발송 작업(kiwoom.yml)이 사진 → 제목 → 본문 세 번에 나눠 보낸다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
REPO = "realmanbae183/kr-radar"
BASE = "kr-radar/kr-radar/state"
LINE = "-" * 50
END_REVIEW = "이 글은 제 개인 기록일 뿐 투자 권유가 아닙니다."
END_FORMAL = ["추가로 궁금한 종목은 댓글로 알려주세요!!",
              "팔로우 하시고 내일 주가 예측글 받아보십쇼!! ❤️",
              "",
              "이 글은 제 개인 기록일 뿐 매수/매도 권유가 아닙니다.",
              "모든 투자 판단과 책임은 본인에게 있습니다."]
KR_TAGS = "#투자 #주식 #경제 #경제적자유 #코스피"
HOLIDAYS = {"2026-12-25", "2026-12-31", "2027-01-01", "2027-02-08", "2027-02-09", "2027-02-10", "2027-03-01"}
DOW = "월화수목금토일"
SHORT = {"kospi": "코스피", "samsung": "삼성전자", "hynix": "SK하이닉스", "enerbility": "두산에너빌리티", "semco": "삼성전기"}


# ───────── 공통 ─────────
def gh(path: str, out: str | None = None, raw: bool = False) -> bytes:
    cmd = ["gh", "api"] + (["-H", "Accept: application/vnd.github.raw"] if raw else []) + [path]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.decode()[:200]}")
    if out:
        open(out, "wb").write(r.stdout)
    return r.stdout


def won(v, index=False, dec=None) -> str:
    if v is None:
        return ""
    if dec is None:
        dec = 0
    s = f"{v:,.{dec}f}"
    return s


def unit(it) -> str:
    return "포인트" if it.get("index") else "원"


def P(v, it, dec=0) -> str:
    return won(v, dec=dec) + unit(it)


def next_day(d: str) -> date:
    x = date.fromisoformat(d) + timedelta(days=1)
    while x.weekday() >= 5 or x.isoformat() in HOLIDAYS:
        x += timedelta(days=1)
    return x


def mdw(x: date) -> str:
    return f"{x.month}월 {x.day}일({DOW[x.weekday()]})"


def key_of(file: str) -> str:            # "2-samsung" → "samsung"
    return file.split("-", 1)[1]


def load(work, name):
    p = os.path.join(work, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


# ───────── fetch ─────────
def cmd_fetch(work: str) -> None:
    os.makedirs(work, exist_ok=True)
    todo = [(f"{BASE}/daily/daily.json", "daily.json"), (f"{BASE}/daily/review/review.json", "review.json"),
            (f"{BASE}/brief/kiwoom/signals.json", "signals.json"), (f"{BASE}/brief/kr.json", "kr.json"),
            (f"{BASE}/brief/kr.png", "kr.png")]
    for src, dst in todo:
        try:
            gh(f"repos/{REPO}/contents/{src}", os.path.join(work, dst), raw=True)
        except RuntimeError as e:
            print("없음:", dst, e)
    d, rv, sg = load(work, "daily.json"), load(work, "review.json"), load(work, "signals.json")
    for it in (d or {}).get("items", []):
        try:
            gh(f"repos/{REPO}/contents/{BASE}/daily/{it['file']}.png", os.path.join(work, it["file"] + ".png"), raw=True)
        except RuntimeError as e:
            print("그림 없음", it["file"], e)
    for it in (rv or {}).get("items", []):
        try:
            gh(f"repos/{REPO}/contents/{BASE}/daily/review/{it['image']}", os.path.join(work, it["image"]), raw=True)
        except RuntimeError as e:
            print("점검 그림 없음", it["image"], e)
    for s in (sg or {}).get("signals", []):
        if s.get("image"):
            gh(f"repos/{REPO}/contents/{BASE}/brief/kiwoom/{s['image']}", os.path.join(work, s["image"]), raw=True)
    if sg and sg.get("guru_image"):
        gh(f"repos/{REPO}/contents/{BASE}/brief/kiwoom/{sg['guru_image']}", os.path.join(work, "guru.png"), raw=True)
    print("받음:", sorted(os.listdir(work)))
    print(status(work))


def status(work) -> str:
    """재료가 오늘 것인지 한 줄씩."""
    today = datetime.now(KST).date().isoformat()
    d, rv, sg, kr = load(work, "daily.json"), load(work, "review.json"), load(work, "signals.json"), load(work, "kr.json")
    out = []
    out.append(f"daily: made={d and d.get('made')} fresh={d and d.get('fresh')} → {'오늘' if d and d.get('made','').startswith(today) else '아님'}")
    out.append(f"review: made={rv and rv.get('made')} day={rv and rv.get('day')} items={len((rv or {}).get('items', []))} fails={(rv or {}).get('fails')}")
    out.append(f"signals: made={sg and sg.get('made')} 신호 {len((sg or {}).get('signals', []))}개")
    t = (kr or {}).get("today", {})
    out.append(f"kr: made={kr and kr.get('made')} day={t.get('day')} closed={t.get('closed')} status={[i.get('status') for i in t.get('idx', [])]}")
    return "\n".join(out)


# ───────── 근거 문구 다듬기 ─────────
def clean_why(w: str) -> tuple[int, str]:
    """daily.json levels.why 한 줄 → (순서, 짧은 근거). 차트 근거가 먼저, 피봇 계산값은 뒤."""
    m = re.match(r"피봇 (\d)차 (저항|지지)선 ([\d,.]+)", w)
    if m:
        return 9, f"피봇 {m.group(1)}차 {m.group(2)} {m.group(3)}"
    m = re.match(r"근처 매물대\(([\d,.]+)~([\d,.]+)\)", w)
    if m:
        return 1, f"매물대 {m.group(1)}~{m.group(2)} 한가운데"
    m = re.match(r"근처 (.+?)\(([\d,.]+)\)에 맞춤", w)
    if m:
        return 1, f"{m.group(1)} {m.group(2)}"
    m = re.match(r"1차와 너무 붙어 그 다음 선인 (.+?)\(([\d,.]+)\)로", w)
    if m:
        return 1, f"{m.group(1)} {m.group(2)}"
    m = re.match(r"1차와 너무 붙어 1차에서 하루 평균 변동폭의 ([\d.]+)배 더", w)
    if m:
        return 5, f"받쳐줄 차트 자리 없음, 1차에서 하루 변동폭 {m.group(1)}배 더"
    return 3, w


def reasons(lv: dict) -> str:
    rs = sorted(clean_why(w) for w in lv.get("why", []))
    return ", ".join(r for _, r in rs) or "근거 없음"


def thick(share) -> str:
    if share is None:
        return ""
    return "얇은 편" if share < 2 else ("두꺼운 편" if share >= 5 else "보통")


def scenario_lines(it: dict) -> list[str]:
    L, c, atr, u = it["levels"], it["today"]["close"], it["levels"].get("atr") or 0, unit(it)
    f = lambda v: won(v)
    up, dn, fl = L["up"], L["down"], L["flat"]
    out = ["상승 시나리오", f"{f(up[0]['price'])} ~ {f(up[1]['price'])}{u}", ""]
    out.append(f"{f(up[0]['price'])} - {reasons(up[0])}")
    out.append(f"{f(up[1]['price'])} - {reasons(up[1])}")
    if L.get("up_more"):
        far = (L["up_more"]["price"] - c) > 2 * atr
        out.append(f"{f(L['up_more']['price'])} - 종가로 {f(up[1]['price'])} 넘기면 {L['up_more']['why']}까지" + (", 다만 현실적으론 먼 거리" if far else ""))
    if L.get("volume_share_to_up1") is not None:
        out.append(f"종가에서 1차 저항까지 매물 {L['volume_share_to_up1']}% - {thick(L['volume_share_to_up1'])}")
    out += ["", "횡보 시나리오", f"{f(fl[0])} ~ {f(fl[1])}{u}", ""]
    out += ["하락 시나리오", f"{f(dn[0]['price'])} ~ {f(dn[1]['price'])}{u}", ""]
    out.append(f"{f(dn[0]['price'])} - {reasons(dn[0])}")
    out.append(f"{f(dn[1]['price'])} - {reasons(dn[1])}")
    if L.get("down_more"):
        far = (c - L["down_more"]["price"]) > 2 * atr
        out.append(f"{f(L['down_more']['price'])} - 종가로 {f(dn[1]['price'])} 깨지면 {L['down_more']['why']}까지" + (", 다만 현실적으론 먼 거리" if far else ""))
    if L.get("volume_share_to_dn1") is not None:
        out.append(f"종가에서 1차 지지까지 매물 {L['volume_share_to_dn1']}% - {thick(L['volume_share_to_dn1'])}")
    return out


# ───────── facts ─────────
def review_marks(rv_item: dict) -> tuple[list, dict]:
    """review.json 에 marks/summary 가 없으면(옛 재료) kr-radar 의 review.py 와 같은 계산을 못 하므로 빈 값."""
    return rv_item.get("marks") or [], rv_item.get("summary") or {}


def build_facts(work: str) -> dict:
    d, rv, sg, kr = load(work, "daily.json"), load(work, "review.json"), load(work, "signals.json"), load(work, "kr.json")
    rmap = {x["file"]: x for x in (rv or {}).get("items", [])}
    facts = {"stocks": [], "sigs": [], "guru": None, "kr": None}
    for i, it in enumerate((d or {}).get("items", []), 1):
        k = key_of(it["file"])
        N = next_day(it["date"])
        now, yd, t = it["now"], it["yesterday"], it["today"]
        dec = 2 if it.get("index") else 0
        st = {"key": k, "no": i, "name": it["name"], "file": it["file"], "index": it.get("index"), "unit": unit(it),
              "day": it["day"], "next": mdw(N), "check_ok": bool((it.get("check") or {}).get("ok")),
              "today": t, "yesterday_chg_pct": yd.get("chg_pct"),
              "ind": {k2: (yd.get(k2), now.get(k2)) for k2 in ("rsi", "rsi_sig", "macd", "macd_sig", "macd_hist", "vol_mult", "ma5", "ma20", "ma60", "ma120", "bb_up", "bb_dn")},
              "cloud_pos": now.get("cloud_pos"), "events": it.get("events", []), "watch": it.get("watch", []),
              "pivot_hit_1y": it.get("pivot_hit_1y"), "scenario": scenario_lines(it)}
        r = rmap.get(it["file"])
        if r and r.get("check_ok", True):
            ms, sm = review_marks(r)
            st["review"] = {"day": r["day"], "prev_up": r["prev"]["up"], "prev_down": r["prev"]["down"], "prev_flat": r["prev"]["flat"],
                            "today": r["today"], "side": sm.get("side"), "verdict": sm.get("verdict"), "breaks": sm.get("breaks", []),
                            "marks": [{"text": f"{m['at']} {m['txt']}", "line": m.get("line"), "nth": m.get("nth"), "kind": m.get("kind"),
                                       "move_pct": m.get("move_pct"), "move_dir": m.get("move_dir")} for m in ms],
                            "image": r.get("image")}
        st["dec"] = dec
        facts["stocks"].append(st)
    if sg:
        for n, s in enumerate(sg.get("signals", []), 1):
            if not s.get("image"):
                continue
            facts["sigs"].append({"n": n, **{k: s.get(k) for k in ("name", "close", "chg_pct", "overlap", "flags", "rsi", "gap_from_ma20_pct",
                                                                     "depth", "trend120_up", "market_breadth_pct", "grade", "grade_up_reason",
                                                                     "past_same_state", "verdict", "image", "rank_by_marcap")}})
        dmap = {it["name"]: it["today"] for it in (d or {}).get("items", [])}
        for x in facts["sigs"]:                     # 레이더 종가가 데일리(KRX) 종가와 다르면 그 신호는 올리지 않는다
            t = dmap.get(x["name"])
            if t and (round(t["close"]) != round(x["close"] or 0) or round(t["chg_pct"], 2) != round(x["chg_pct"] or 0, 2)):
                x["mismatch"] = f"레이더 {x['close']}/{x['chg_pct']}% vs 데일리 {t['close']}/{t['chg_pct']}%"
        facts["new_os_total"] = sg.get("new_os_total")
        q = sg.get("quote") or {}
        facts["guru"] = {"text": q.get("text"), "who": q.get("who")}
    if kr:
        t = kr.get("today", {})
        facts["kr"] = {"date": t.get("date"), "dow": t.get("dow"), "day": t.get("day"), "closed": t.get("closed"),
                       "idx": [(x["n"], x["v"], x["p"], x.get("hi"), x.get("lo")) for x in t.get("idx", [])],
                       "flow": [(x[0], x[2]) for x in t.get("flow", [])],
                       "glob": [(x["n"], x["v"], x.get("p")) for x in t.get("glob", [])],
                       "sec": [(x[0].replace("<br>", " "), x[1]) for x in t.get("sec", [])],
                       "market": kr.get("market"), "thermo": kr.get("thermo"), "mood": t.get("mood")}
    return facts


def facts_text(F: dict) -> str:
    o = []
    for s in F["stocks"]:
        dec = s["dec"]
        t = s["today"]
        f = lambda v, dd=dec: won(v, dec=dd)
        o.append(f"━━ [{s['key']}] {s['name']} ({s['unit']})  오늘 {s['day']} → 내일 {s['next']}  대조 {'OK' if s['check_ok'] else '불일치(시가·고가·저가 쓰지 말 것)'}")
        o.append(f"오늘 종가 {f(t['close'])} ({t['chg_pct']:+.2f}%, {f(t['chg'])}), 시가 {f(t['open'])} 고가 {f(t['high'])} 저가 {f(t['low'])}, 어제 등락 {s['yesterday_chg_pct']:+.2f}%")
        r = s.get("review")
        if r:
            o.append(f"[점검] 어제 선: 상방 {[f(x, 0) for x in r['prev_up']]} 횡보 {[f(x, 0) for x in r['prev_flat']]} 하방 {[f(x, 0) for x in r['prev_down']]}")
            o.append(f"  간 쪽: {r['side']}  판정: {r['verdict']}")
            for m in r["marks"]:
                o.append(f"  동그라미: {m['text']} → 그 뒤 {m['move_pct']}% {m['move_dir']} ({m['nth']} {m['kind']})")
            for b in r["breaks"]:
                o.append(f"  뚫림: {b}")
        else:
            o.append("[점검] 재료 없음 → 점검 글 안 씀")
        I = s["ind"]
        g = lambda k, dd=1: f"{won(I[k][0], dec=dd)}→{won(I[k][1], dec=dd)}"
        o.append(f"[지표] RSI {g('rsi')} (시그널 {won(I['rsi_sig'][1], dec=1)}) / MACD {g('macd', 0)} 시그널 {won(I['macd_sig'][1], dec=0)} 막대 {g('macd_hist', 0)} / 거래량 20일 평균의 {g('vol_mult', 2)}배")
        o.append(f"  5일선 {f(I['ma5'][1], 0)} 20일선 {f(I['ma20'][1], 0)} 60일선 {f(I['ma60'][1], 0)} 120일선 {f(I['ma120'][1], 0)} 볼린저 {f(I['bb_dn'][1], 0)}~{f(I['bb_up'][1], 0)} 구름대 {s['cloud_pos']}")
        if s["events"]:
            o.append(f"  오늘 생긴 일: {' / '.join(s['events'])}")
        if s["watch"]:
            o.append(f"  곧 생길 수 있는 일: {' / '.join(s['watch'])}")
        ph = s.get("pivot_hit_1y") or {}
        if ph:
            o.append(f"  1년 {ph.get('days')}일 중 다음 날 1차 저항 닿음 {ph.get('up1_touch')}번, 1차 지지 닿음 {ph.get('dn1_touch')}번")
        o.append("[내일 예상 - 코드가 넣는 시나리오 칸]")
        o += ["  " + x for x in s["scenario"] if x]
        o.append("")
    for s in F["sigs"]:
        ps = s["past_same_state"] or {}
        o.append(f"━━ [sig{s['n']}] {s['name']} {s['grade']}등급({s['verdict']}) 종가 {won(s['close'])}원 {s['chg_pct']:+.2f}% 겹친 조건 {s['overlap']}개 {s['flags']} "
                 f"RSI {s['rsi']} 20일선 거리 {s['gap_from_ma20_pct']}% ({s['depth']}) 120일선 {'오름' if s['trend120_up'] else '내림'} "
                 f"시장 폭 {s['market_breadth_pct']}% 과거 {ps.get('count')}번 5일 {ps.get('win5_pct')}%/{ps.get('avg5_pct')}% 20일 {ps.get('win20_pct')}%/{ps.get('avg20_pct')}% "
                 f"등급 이유 {s['grade_up_reason']} 시총 순위 {s['rank_by_marcap']}" + (f"  ※ 시세 불일치 → 글 쓰지 말 것 ({s['mismatch']})" if s.get("mismatch") else ""))
    if F["sigs"]:
        o.append(f"오늘 새 과매도 종목 {F.get('new_os_total')}개\n")
    if F.get("guru"):
        o.append(f"━━ [guru] \"{F['guru']['text']}\" — {F['guru']['who']}\n")
    k = F.get("kr")
    if k:
        o.append(f"━━ [kr] {k['date']} ({k['dow']}) 마감 closed={k['closed']}")
        o.append(f"  지수: " + " / ".join(f"{n} {won(v, dec=2)} ({p:+.2f}%) 고 {won(h, dec=2)} 저 {won(l, dec=2)}" for n, v, p, h, l in k["idx"]))
        o.append(f"  수급(억, +순매수): " + " / ".join(f"{n} {won(v)}" for n, v in k["flow"]))
        o.append(f"  환율·지표: " + " / ".join(f"{n} {v} ({p:+.2f}%)" for n, v, p in k["glob"] if p is not None))
        o.append(f"  업종: " + " / ".join(f"{n} {p:+.2f}%" for n, p in k["sec"]))
        m, th = k.get("market") or {}, k.get("thermo") or {}
        o.append(f"  시장 폭 {m.get('breadth')}% (20일선 위 {m.get('above')}/{m.get('stocks')}), 코스피 20일선 대비 {m.get('vs20')}% 120일선 대비 {m.get('vs120')}% "
                 f"20일선 위 {m.get('up20')} 120일선 위 {m.get('up120')} / 오른 {th.get('up')} 내린 {th.get('down')} 신고가 {th.get('hi52')} 신저가 {th.get('lo52')}")
        if k.get("mood"):
            o.append(f"  예탁금·신용: {k['mood']}")
    return "\n".join(o)


def cmd_facts(work: str) -> None:
    F = build_facts(work)
    json.dump(F, open(os.path.join(work, "facts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    txt = facts_text(F)
    open(os.path.join(work, "facts.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


# ───────── inbox ─────────
def cmd_inbox(work: str, done_path: str) -> None:
    done = set(json.load(open(done_path, encoding="utf-8"))) if os.path.exists(done_path) else set()
    today = datetime.now(KST).date()
    cut = datetime.combine(today, datetime.min.time(), KST).replace(hour=15, minute=30)
    os.makedirs(os.path.join(work, "inbox"), exist_ok=True)
    days = json.loads(gh(f"repos/{REPO}/contents/inbox?ref=inbox"))
    days = sorted(x["name"] for x in days if x["type"] == "dir" and x["name"] >= (today - timedelta(days=7)).isoformat())
    picked = []
    for dd in days:
        for x in json.loads(gh(f"repos/{REPO}/contents/inbox/{dd}?ref=inbox")):
            if not x["name"].endswith(".json") or f"{dd}/{x['name']}" in done:
                continue
            j = json.loads(gh(f"repos/{REPO}/contents/inbox/{dd}/{x['name']}?ref=inbox", raw=True))
            if datetime.fromisoformat(j["received"]) >= cut:
                continue
            stem = x["name"][:-5]
            local = os.path.join(work, "inbox", f"{dd}_{stem}")
            json.dump(j, open(local + ".json", "w", encoding="utf-8"), ensure_ascii=False)
            img = None
            if j.get("photo"):
                try:
                    gh(f"repos/{REPO}/contents/inbox/{dd}/{stem}.jpg?ref=inbox", local + ".jpg", raw=True)
                    img = local + ".jpg"
                except RuntimeError:
                    pass
            picked.append({"src": f"{dd}/{x['name']}", "received": j["received"], "chars": len(j.get("text") or ""), "photo": img})
    json.dump(picked, open(os.path.join(work, "inbox.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p in picked:
        print(p["src"], p["received"], f"{p['chars']}자", "사진 " + p["photo"] if p["photo"] else "사진 없음")
    print(f"남은 원문 {len(picked)}개 (본문은 WORK/inbox/*.json 의 text, 사진은 같은 이름 .jpg)")


# ───────── 숫자 검사 ─────────
NUM = re.compile(r"(?<![\d.])[-+]?\d[\d,]*(?:\.\d+)?")


def nums_in(s: str) -> list[float]:
    out = []
    for m in NUM.finditer(s):
        try:
            out.append(float(m.group().replace(",", "")))
        except ValueError:
            pass
    return out


def allowed_from(*objs) -> set:
    S = set()
    def add(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            for d in (0, 1, 2):
                r = round(abs(float(v)), d)
                S.add(r)
            import math
            S.add(float(math.floor(abs(v)))); S.add(float(math.ceil(abs(v))))
        elif isinstance(v, str):
            for x in nums_in(v):
                add(x)
            for x in re.findall(r"\d{1,2}:\d{2}", v):
                h, m = x.split(":")
                add(int(h)); add(int(m)); add(int(h) - 12 if int(h) > 12 else int(h))
        elif isinstance(v, dict):
            for x in v.values():
                add(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                add(x)
    for o in objs:
        add(o)
    for i in range(0, 11):
        S.add(float(i))
    S.update({20.0, 30.0, 50.0, 60.0, 70.0, 80.0, 100.0, 120.0, 250.0})   # 지표 기준값(RSI 30, 5·20·60·120일선, 1년 250일 등)
    return S


def check_nums(text: str, allowed: set, where: str, probs: list) -> None:
    """소수점이 있는 숫자는 그 자릿수까지 재료와 같아야 하고, 정수는 재료 값의 반올림·올림·내림까지 허용 ('5% 가까이' 같은 말)."""
    for m in NUM.finditer(text):
        g = m.group().replace(",", "")
        try:
            x = float(g)
        except ValueError:
            continue
        if round(abs(x), 2) not in allowed:
            probs.append(f"{where}: 숫자 {m.group()} 가 재료에 없음 → 고치거나 빼기")


# ───────── build ─────────
def body(*parts: str) -> str:
    """본문은 항상 빈 줄 하나로 시작 (보낼 때 맨 앞 빈 줄이 지워지지 않게 발송 작업이 보이지 않는 문자를 붙인다)."""
    return "\n" + "\n\n".join(p.strip("\n") for p in parts if p and p.strip()) + "\n"


def write_md(path: str, title: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(title.strip() + "\n" + text)


def cmd_build(work: str, slots_path: str, kp: str, what: str = "all") -> None:
    F = json.load(open(os.path.join(work, "facts.json"), encoding="utf-8"))
    S = json.load(open(slots_path, encoding="utf-8"))
    kr = load(work, "kr.json")
    D = load(work, "daily.json")["items"][0]["date"]
    probs: list[str] = []
    made: list[str] = []
    kdir = os.path.join(kp, "kiwoom", D)
    os.makedirs(kdir, exist_ok=True)

    # 국장 시황 (posts → send 작업이 텔레그램 + 인스타)
    if what in ("all", "kr") and F.get("kr") and S.get("kr"):
        k = F["kr"]
        dd = date.fromisoformat(k["day"])
        title = f"{dd.month}월 {dd.day}일 ({DOW[dd.weekday()]}) 오늘의국장"
        txt = body(S["kr"]["body"])
        check_nums(S["kr"]["body"], allowed_from(k), "국장 시황", probs)
        os.makedirs(os.path.join(kp, "posts"), exist_ok=True); os.makedirs(os.path.join(kp, "media"), exist_ok=True)
        write_md(os.path.join(kp, "posts", f"{D}-kr.md"), title, txt)
        open(os.path.join(kp, "posts", f"{D}-kr.ig.txt"), "w", encoding="utf-8").write(f"{title}\n\n{S['kr']['body'].strip()}\n\n{KR_TAGS}\n")
        shutil.copy(os.path.join(work, "kr.png"), os.path.join(kp, "media", f"{D}-kr.png"))
        shutil.copy(os.path.join(work, "kr.json"), os.path.join(kp, "media", f"{D}-kr.json"))
        if os.path.exists(os.path.join(work, "guru.png")):
            shutil.copy(os.path.join(work, "guru.png"), os.path.join(kp, "media", f"{D}-kr-guru.png"))   # 인스타 구루 스토리용
        made += [f"posts/{D}-kr.md", f"posts/{D}-kr.ig.txt", f"media/{D}-kr.png", f"media/{D}-kr.json", f"media/{D}-kr-guru.png"]

    blog2 = []
    if what in ("all", "kiwoom"):
        # 종목 세트: 점검(a) → 내일 예상(b)
        for s in F["stocks"]:
            sl = (S.get("stocks") or {}).get(s["key"]) or {}
            allowed = allowed_from(s)
            n = s["no"]
            rv = s.get("review")
            if rv and sl.get("review_open"):
                lines = [m["text"] for m in rv["marks"]] or rv["breaks"]
                for kx in ("review_open", "review_imagine"):
                    if sl.get(kx):
                        check_nums(sl[kx], allowed, f"{s['name']} 점검 {kx}", probs)
                txt = body(sl["review_open"], "\n".join(lines), sl.get("review_imagine", ""), END_REVIEW)
                name = f"1{n}a-{s['key']}-review"
                write_md(os.path.join(kdir, name + ".md"), f"{rv['day']} {s['name']} 어제 예상 점검", txt)
                if rv.get("image") and os.path.exists(os.path.join(work, rv["image"])):
                    shutil.copy(os.path.join(work, rv["image"]), os.path.join(kdir, name + ".png"))
                made.append(name)
                blog2.append(("review", s, txt, os.path.join(kdir, name + ".png")))
            elif rv:
                probs.append(f"{s['name']} 점검 글 칸(review_open)이 비어 있음")
            if sl.get("fc_first"):
                for kx in ("fc_first", "fc_indicator", "fc_greet"):
                    if sl.get(kx):
                        check_nums(sl[kx], allowed, f"{s['name']} 예상 {kx}", probs)
                txt = body(sl["fc_first"], "\n".join(s["scenario"]), LINE, sl.get("fc_indicator", ""), LINE,
                           sl.get("fc_greet", ""), "\n".join(END_FORMAL))
                name = f"1{n}b-{s['key']}"
                write_md(os.path.join(kdir, name + ".md"), f"{s['next']} {s['name']} 내일 예상", txt)
                if os.path.exists(os.path.join(work, s["file"] + ".png")):
                    shutil.copy(os.path.join(work, s["file"] + ".png"), os.path.join(kdir, name + ".png"))
                made.append(name)
                blog2.append(("forecast", s, txt, os.path.join(kdir, name + ".png")))
            else:
                probs.append(f"{s['name']} 내일 예상 칸(fc_first)이 비어 있음")
        # 과매도
        for s in F["sigs"]:
            if s.get("mismatch"):
                probs.append(f"레이더 {s['name']} 시세 불일치로 안 올림 ({s['mismatch']}) → PushNotification 으로 알리기"); continue
            sl = (S.get("sigs") or {}).get(str(s["n"])) or {}
            if not sl.get("first"):
                probs.append(f"레이더 {s['name']} 칸(first)이 비어 있음"); continue
            allowed = allowed_from(s, F.get("new_os_total"))
            for kx in ("first", "comment"):
                if sl.get(kx):
                    check_nums(sl[kx], allowed, f"레이더 {s['name']} {kx}", probs)
            fl, ps = s["flags"] or {}, s["past_same_state"] or {}
            sig = [f"겹친 신호 {s['overlap']}개"]
            if fl.get("rsi"):
                sig.append(f"RSI 30 아래 - {s['rsi']}")
            if fl.get("bb"):
                sig.append("볼린저 하단 이탈 - 하단 밖에서 마감")
            if fl.get("gap"):
                sig.append(f"20일선과의 거리 - {s['gap_from_ma20_pct']}%")
            past = [f"과거 같은 상태 {ps.get('count'):,}번",
                    f"5일 뒤 상승 확률 - {ps.get('win5_pct')}%, 평균 {ps.get('avg5_pct'):+}%",
                    f"20일 뒤 상승 확률 - {ps.get('win20_pct')}%, 평균 {ps.get('avg20_pct'):+}%"]
            txt = body(sl["first"], "\n".join(sig), "\n".join(past), sl.get("comment", ""), "\n".join(END_FORMAL))
            name = f"6{s['n']}-sig{s['n']}"
            write_md(os.path.join(kdir, name + ".md"), f"오늘 버거대왕 레이더 {s['grade']}등급, {s['name']}", txt)
            shutil.copy(os.path.join(work, s["image"]), os.path.join(kdir, name + ".png"))
            made.append(name)
        # 구루
        if F.get("guru") and os.path.exists(os.path.join(work, "guru.png")):
            g = (S.get("guru") or {}).get("body")
            if g:
                write_md(os.path.join(kdir, "70-guru.md"), "버거대왕이 전하는 구루의 한마디", body(g))
                shutil.copy(os.path.join(work, "guru.png"), os.path.join(kdir, "70-guru.png"))
                made.append("70-guru")
            else:
                probs.append("구루 칸(guru.body)이 비어 있음")

    # 수집함 원문 → 키움 글
    if what in ("all", "notes"):
        for i, nt in enumerate(S.get("notes") or [], 1):
            name = f"8{i:02d}-note"
            write_md(os.path.join(kdir, name + ".md"), nt["title"], body(nt["body"]))
            src = os.path.join(work, "inbox", nt["src"].replace("/", "_").replace(".json", ".jpg"))
            if os.path.exists(src):
                shutil.copy(src, os.path.join(kdir, name + ".jpg"))
            made.append(name)

    if blog2:
        json.dump([{"kind": k, "key": s["key"], "name": s["name"], "text": t, "img": im if os.path.exists(im) else None}
                   for k, s, t, im in blog2], open(os.path.join(work, "blog2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("만든 것:", " ".join(made))
    if probs:
        print("\n확인 필요:")
        for p in probs:
            print(" -", p)
        sys.exit(2)
    print("숫자 검사 통과")


# ───────── blog ─────────
def cmd_blog(blocks_path: str, out: str) -> None:
    os.environ["BLOG_OUT"] = out
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib
    import blog_render
    importlib.reload(blog_render)
    B = json.load(open(blocks_path, encoding="utf-8"))
    blocks = [tuple(b) for b in B["blocks"]]
    blog_render.render(B["name"], B["title"], blocks, B["tags"])


def cmd_blog2(work: str, out: str, key_line: str, end_line: str) -> None:
    """블로그 2편(예상과 피드백)은 키움 글을 그대로 담으므로 코드가 만든다. 제목·태그도 정해진 꼴."""
    items = json.load(open(os.path.join(work, "blog2.json"), encoding="utf-8"))
    F = json.load(open(os.path.join(work, "facts.json"), encoding="utf-8"))
    nx = F["stocks"][0]["next"]
    m = re.match(r"(\d+)월 (\d+)일", nx)
    names = [s["name"] for s in F["stocks"] if not s.get("index")]
    title = f"[{m.group(1)}/{m.group(2)} 국장 예상] 코스피 주가 전망, {'·'.join(names[:3])} 주가 내일 예상 | 지지선 저항선"
    def strip_end(t):
        drop = (set(END_FORMAL) - {""}) | {END_REVIEW, LINE}
        keep = [l for l in t.strip().split("\n") if l.strip() not in drop]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()
    blocks = [["key", key_line]]
    for s in F["stocks"]:
        mine = [x for x in items if x["key"] == s["key"]]
        if not mine:
            continue
        blocks.append(["topic", f"{s['name']} 주가 내일 예상, 지지선·저항선 (어제 결과)"])
        for x in mine:
            blocks.append(["p", "■ 어제 예상 점검" if x["kind"] == "review" else "■ 내일 예상"])
            if x["img"]:
                blocks.append(["img", x["img"], f"{s['name']} {'어제 점검' if x['kind'] == 'review' else '내일 예상'}"])
            blocks.append(["p", strip_end(x["text"])])
        blocks.append(["hr", ""])
    blocks.append(["p", end_line])
    tags = " ".join("#" + t for t in (["코스피", "코스피주가", "코스피전망", "코스피지수", "코스피야간선물", "주식", "국내주식", "내일주가", "지지선", "저항선"]
                                       + [f"{n.replace(' ', '')}{suf}" for n in names for suf in ("", "주가", "주가전망", "목표주가", "실적발표")])[:30])
    B = {"name": "daily-2-forecast", "title": title, "blocks": blocks, "tags": tags}
    p = os.path.join(work, "blog2_blocks.json")
    json.dump(B, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cmd_blog(p, out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    c = a[0]
    if c == "fetch":
        cmd_fetch(a[1])
    elif c == "status":
        print(status(a[1]))
    elif c == "facts":
        cmd_facts(a[1])
    elif c == "inbox":
        cmd_inbox(a[1], a[2])
    elif c == "build":
        cmd_build(a[1], a[2], a[3], a[4] if len(a) > 4 else "all")
    elif c == "blog":
        cmd_blog(a[1], a[2])
    elif c == "blog2":
        cmd_blog2(a[1], a[2], a[3], a[4])
    else:
        print(__doc__); sys.exit(1)
