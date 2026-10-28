"""照 song.json 的和弦（每小節前後半各一個）輸出和弦譜 md 與「旋律＋和弦」試聽 wav，給使用者確認和弦。

用法：python chords.py <song.json> [--key C] [--bpm 110] [--out 資料夾]
弱起小節不配和弦。和弦可先用 compare.py 從原錄音推，再照旋律音手修。
"""
import argparse
from pathlib import Path

import numpy as np

from song import BAR, Song, write_wav


def render(song, bpm, sr=44100):
    sec16 = 60 / bpm / 4
    evs = song.events()
    total = int(song.length16() * sec16 * sr) + sr
    y = np.zeros(total)

    def tone(f, n, decay, harm):
        t = np.arange(n) / sr
        s = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in harm)
        return s * np.minimum(1, t / 0.01) * np.exp(-t * decay) * np.minimum(1, (n / sr - t) / 0.05)

    for t, d, m, *_ in evs:  # 旋律
        if m is not None:
            n = int(d * sec16 * sr)
            s = int(t * sec16 * sr)
            y[s:s + n] += tone(440 * 2 ** ((m - 69) / 12), n, 1.8, ((1, 1.0), (2, 0.35), (3, 0.15)))
    last_len = song.length16() - song.pickup_len - (len(song.bars) - 1) * BAR
    for i, halves in enumerate(song.chart):  # 和弦：低八度柱式＋根音
        for h, name in enumerate(halves):
            if name is None:
                continue
            t0 = song.pickup_len + i * BAR + h * 8
            n = int((last_len if i == len(song.chart) - 1 and h == 0 and halves[1] is None else 8) * sec16 * sr)
            s = int(t0 * sec16 * sr)
            _, pcs, bass = song.chord(name)
            for k, pc in enumerate(pcs):
                m = 48 + pc + (12 if k and pc < pcs[0] else 0)
                y[s:s + n] += 0.22 * tone(440 * 2 ** ((m - 69) / 12), n, 1.2, ((1, 1.0), (2, 0.2)))
            y[s:s + n] += 0.35 * tone(440 * 2 ** ((36 + bass - 69) / 12), n, 1.0, ((1, 1.0), (2, 0.3)))
    return y / np.abs(y).max() * 0.8


def chart_text(song):
    evs = song.events()
    rows = []
    for i, (a, b) in enumerate(song.chart):
        words = []
        for half in (0, 1):
            t0 = song.pickup_len + i * BAR + half * 8
            words.append("".join(ch for t, d, m, ch, py, first, _ in evs if first and m is not None and t0 <= t < t0 + 8))
        na = song.chord(a)[0]
        nb = song.chord(b)[0] if b else ""
        rows.append(f"| {i + 1} | {na} | {words[0]} | {nb} | {words[1]} |")
    return "| 小節 | 前半和弦 | 歌詞 | 後半和弦 | 歌詞 |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--key")
    ap.add_argument("--bpm", type=float, default=110)
    ap.add_argument("--out")
    a = ap.parse_args()
    song = Song(a.song, a.key)
    out = Path(a.out) if a.out else song.path.parent
    write_wav(out / f"旋律加和弦試聽_{song.key}調_{a.bpm:g}BPM.wav", render(song, a.bpm))
    text = chart_text(song)
    (out / f"和弦譜_{song.key}調.md").write_text(f"# {song.title} 和弦譜（{song.key} 調，弱起不配和弦）\n\n" + text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
