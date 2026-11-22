"""버거대왕 차트 릴스용 배경음악 3곡 (긴박하지만 귀 안 아프게). 30초, 44.1kHz 스테레오."""
import numpy as np, subprocess, os
from scipy.signal import butter, sosfilt

SR = 44100
OUT = "/home/claude/music/out"
os.makedirs(OUT, exist_ok=True)


def lp(x, hz, order=2):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def hp(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / r)
    return e


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    s = 0
    for d in (-detune, 0, detune):
        ph = (t * f * (1 + d)) % 1.0
        s = s + (2 * ph - 1)
    return s / 3


def kick(n):
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)


def hat(n, rng):
    return hp(rng.standard_normal(n), 7000) * env(n, 0.001, 0.025)


def snare(n, rng):
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    noise = lp(hp(rng.standard_normal(n), 1500), 6000) * np.exp(-t * 18)
    return 0.5 * body + 0.6 * noise


def track(name, bpm, root, prog, arp, seed, bright):
    rng = np.random.default_rng(seed)
    dur = 30.0
    N = int(SR * dur)
    L = np.zeros(N); R = np.zeros(N)
    beat = 60 / bpm
    s16 = beat / 4
    bars = int(dur / (beat * 4)) + 1

    def add(sig, t0, gl=1.0, gr=1.0):
        i = int(t0 * SR)
        if i >= N:
            return
        sig = sig[: N - i]
        L[i:i + len(sig)] += sig * gl
        R[i:i + len(sig)] += sig * gr

    for b in range(bars):
        chord = prog[b % len(prog)]
        t_bar = b * beat * 4
        intro = b < 2
        # 패드 (부드럽게 깔림)
        n = int(beat * 4 * SR)
        pad = sum(saw(note(root + 12 + c), n, 0.004) for c in chord) / len(chord)
        pad = lp(pad, 900 + 300 * bright) * np.minimum(1, np.arange(n) / (0.3 * SR)) * 0.16
        add(pad, t_bar, 1.0, 0.85)
        # 베이스 8분음표 (긴박함의 핵심)
        for k in range(8):
            if intro and k % 2:
                continue
            nn = int(s16 * 2 * SR * 0.9)
            bs = saw(note(root - 12 + chord[0]), nn) * env(nn, 0.004, 0.12)
            add(lp(bs, 380) * 0.42, t_bar + k * s16 * 2)
        # 아르페지오 16분음표
        for k in range(16):
            if intro and b == 0:
                break
            iv = arp[k % len(arp)]
            m = root + 24 + chord[iv % len(chord)] + 12 * (iv // len(chord))
            nn = int(s16 * SR)
            a = saw(note(m), nn, 0.003) * env(nn, 0.003, 0.09)
            a = lp(a, 1700 + 900 * bright) * 0.11
            pan = 0.35 * np.sin(k * 0.8)
            add(a, t_bar + k * s16, 1 - pan, 1 + pan)
        # 드럼 (3번째 마디부터)
        if not intro:
            for k in range(4):
                add(kick(int(0.4 * SR)) * 0.55, t_bar + k * beat)
            for k in (1, 3):
                add(snare(int(0.3 * SR), rng) * 0.22, t_bar + k * beat)
            for k in range(8):
                add(hat(int(0.06 * SR), rng) * (0.10 if k % 2 else 0.06), t_bar + k * s16 * 2 + s16, 0.8, 1.0)
    # 마스터: 끝 2초 페이드, 부드러운 고역 정리, 정규화
    mix = np.stack([L, R], 1)
    mix[:, 0] = lp(mix[:, 0], 9000); mix[:, 1] = lp(mix[:, 1], 9000)
    fade = np.ones(N); fade[-2 * SR:] = np.linspace(1, 0, 2 * SR)
    mix *= fade[:, None]
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix = mix / np.max(np.abs(mix)) * 0.85
    wav = f"{OUT}/{name}.wav"
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-16:TP=-1.5",
                    "-c:a", "libmp3lame", "-b:a", "192k", f"{OUT}/{name}.mp3"], check=True)
    os.remove(wav)


# 단조 화음 (근음 기준 반음 간격)
m = [0, 3, 7]
track("1_코스피_긴장", 124, 45, [m, [-4, 0, 3], [-2, 2, 5], [-5, -2, 2]], [0, 1, 2, 1, 3, 2, 1, 2], 1, 0.4)   # A단조
track("2_삼성전자_질주", 132, 50, [m, m, [-4, 0, 3], [-5, -1, 2]], [0, 2, 1, 3, 0, 2, 4, 2], 2, 0.6)        # D단조
track("3_하이닉스_추격", 128, 47, [m, [-2, 2, 5], [-4, 0, 3], [-2, 2, 5]], [0, 1, 2, 3, 2, 1, 4, 1], 3, 0.5)  # B단조
print(os.listdir(OUT))
