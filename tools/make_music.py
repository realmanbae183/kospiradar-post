"""
make_music.py — 시황 영상 배경음을 직접 합성한다 (저작권 걱정 없는 자체 제작).
  python tools/make_music.py            assets/music/{up,calm,down}/ 에 곡을 만든다
분위기 세 가지:
  up    오른 날   — 밝은 장조, 말랑한 건반 소리, 조금 경쾌
  calm  보합 날   — 느긋한 장조, 부드러운 피아노
  down  내린 날   — 단조, 느린 피아노 + 긴 울림 (클래식 소품 느낌)
귀를 찌르는 높은 소리가 나지 않게 5kHz 위는 깎고, 소리 크기도 작게 맞춘다.
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
SEC = 12.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "music")


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def tone(m: float, dur: float, kind: str, vel: float = 1.0) -> np.ndarray:
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = hz(m)
    if kind == "piano":                       # 부드러운 피아노: 배음이 빨리 사그라듦
        y = np.zeros(n)
        for k, a in enumerate([1.0, 0.5, 0.25, 0.12, 0.06], start=1):
            y += a * np.sin(2 * np.pi * f * k * 1.0004 ** k * t) * np.exp(-t * (1.6 + 1.3 * k))
        env = np.minimum(t / 0.006, 1.0) * np.exp(-t * 0.9)
    elif kind == "bell":                      # 말랑한 종/마림바 느낌 (산뜻)
        y = np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) + 0.35 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 6) \
            + 0.12 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 12)
        env = np.minimum(t / 0.004, 1.0)
    else:                                     # pad: 천천히 올라오는 받침 소리
        y = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2 * t)
        env = np.minimum(t / 0.6, 1.0) * np.minimum((dur - t) / 0.8, 1.0).clip(0)
    return y * env * vel


def put(buf: np.ndarray, x: np.ndarray, at: float) -> None:
    i = int(at * SR)
    j = min(len(buf), i + len(x))
    if i < len(buf):
        buf[i:j] += x[: j - i]


def reverb(x: np.ndarray, sec: float, wet: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SR * sec)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * (6.0 / sec))
    ir = sosfilt(butter(2, 3500, fs=SR, output="sos"), ir)
    ir /= np.abs(ir).sum() / 8
    w = fftconvolve(x, ir)[: len(x)]
    return (1 - wet) * x + wet * w


# 코드 진행: 각 마디의 (베이스, [코드 구성음]) — MIDI 번호
UP = {
    "C": [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [57, 60, 64]), (41, [57, 60, 65])],
    "G": [(43, [59, 62, 67]), (50, [57, 62, 66]), (40, [59, 62, 67]), (48, [60, 64, 67])],
    "D": [(50, [57, 62, 66]), (45, [57, 61, 64]), (47, [59, 62, 66]), (43, [59, 62, 67])],
    "F": [(41, [57, 60, 65]), (48, [55, 60, 64]), (50, [57, 62, 65]), (46, [58, 62, 65])],
}
CALM = {
    "Cmaj7": [(48, [55, 59, 64]), (45, [55, 60, 64]), (41, [57, 60, 64]), (43, [55, 59, 62])],
    "Fmaj7": [(41, [57, 60, 64]), (50, [57, 60, 65]), (46, [58, 62, 65]), (48, [55, 60, 64])],
    "Gmaj7": [(43, [59, 62, 66]), (40, [59, 62, 67]), (48, [59, 64, 67]), (50, [57, 62, 66])],
}
DOWN = {
    "Dm": [(50, [57, 62, 65]), (46, [58, 62, 65]), (43, [58, 62, 67]), (45, [57, 61, 67])],
    "Am": [(45, [57, 60, 64]), (41, [57, 60, 65]), (50, [57, 62, 65]), (40, [56, 59, 64])],
    "Em": [(40, [55, 59, 64]), (45, [57, 60, 64]), (47, [54, 59, 63]), (40, [55, 59, 64])],
    "Gm": [(43, [58, 62, 67]), (39, [58, 63, 67]), (48, [55, 60, 63]), (50, [57, 62, 66])],
}


def render(mood: str, name: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    prog = {"up": UP, "calm": CALM, "down": DOWN}[mood][name]
    bpm = {"up": 104, "calm": 76, "down": 58}[mood]
    beat = 60.0 / bpm
    bar = beat * (4 if mood != "down" else 3)
    buf = np.zeros(int((SEC + 3) * SR))
    kind = "bell" if mood == "up" else "piano"
    bi = 0
    t0 = 0.0
    while t0 < SEC:
        bass, ch = prog[bi % 4]
        bi += 1
        put(buf, tone(bass, bar * 1.6, "piano", 0.55), t0)
        if mood == "up":
            order = [0, 1, 2, 1, 0, 1, 2, 1]                       # 8분음표 올라갔다 내려오는 반짝임
            for k, o in enumerate(order):
                put(buf, tone(ch[o] + 12, 1.2, kind, 0.30), t0 + k * beat / 2)
            if rng.random() < 0.8:                                   # 가끔 높은 장식음
                put(buf, tone(ch[2] + 24, 1.4, kind, 0.18), t0 + beat * rng.choice([1.5, 2.5, 3.5]))
            put(buf, tone(ch[0] - 12, bar, "pad", 0.10), t0)
        elif mood == "calm":
            for k, o in enumerate([0, 1, 2, 1, 2, 1, 0, 1]):
                put(buf, tone(ch[o] + 12, 2.0, kind, 0.30), t0 + k * beat / 2)
            put(buf, tone(ch[1] + 24, 2.5, kind, 0.14), t0 + beat * 2)
        else:                                                         # 3박자 느린 피아노, 사티 스타일의 빈 공간
            put(buf, tone(ch[0], 2.5, kind, 0.38), t0 + beat)
            put(buf, tone(ch[1], 2.5, kind, 0.34), t0 + beat * 2)
            put(buf, tone(ch[2] + 12, 3.0, kind, 0.30), t0 + beat * 1.5 + 0.02)
            if rng.random() < 0.6:
                put(buf, tone(ch[1] + 12, 3.0, kind, 0.18), t0 + beat * 2.5)
        t0 += bar
    buf = reverb(buf, {"up": 1.0, "calm": 1.6, "down": 2.6}[mood], {"up": 0.22, "calm": 0.32, "down": 0.45}[mood], seed)
    buf = sosfilt(butter(4, 5000, fs=SR, output="sos"), buf)           # 높은 소리 깎기
    buf = sosfilt(butter(2, 60, btype="high", fs=SR, output="sos"), buf)
    buf = buf[: int(SEC * SR)]
    fade = int(0.4 * SR)
    buf[:fade] *= np.linspace(0, 1, fade)
    buf[-fade * 3:] *= np.linspace(1, 0, fade * 3)
    buf *= 0.6 / (np.abs(buf).max() + 1e-9)
    return buf


def save(x: np.ndarray, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    delay = int(0.012 * SR)                                              # 좌우 살짝 엇갈리게 (넓게 들리도록)
    L = x
    R = np.concatenate([np.zeros(delay), x[:-delay]])
    pcm = (np.stack([L, R], 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "aac", "-b:a", "128k", path], input=pcm, check=True)


def main() -> None:
    sets = {"up": UP, "calm": CALM, "down": DOWN}
    for mood, d in sets.items():
        for i, name in enumerate(d):
            save(render(mood, name, 100 + i), os.path.join(OUT, mood, f"{mood}{i + 1}.m4a"))
            print("만듦:", mood, name)


if __name__ == "__main__":
    main()
