"""拿原錄音核對手打的譜、推和弦（結果只供參考，和弦最後要使用者試聽確認）。

1. 對照試聽：左聲道原錄音、右聲道 song.json 的旋律，對齊第一個字
2. 和弦建議：依小節格線算原錄音每半小節的 chroma（numpy STFT），跟 12 個根音 × 大、小、屬七和弦樣板比對，
   再加上旋律音落在和弦內的比例；人聲干擾大，越接近純伴奏的錄音越準

用法：python compare.py <song.json> <原錄音 wav> --key C --bpm 110.1 --offset 0.265 [--out 資料夾]
- --key：原錄音的調；--bpm、--offset（第一個字在錄音裡的秒數）先聽錄音或看頻譜抓
- 原錄音先用 ffmpeg 轉成 wav：ffmpeg -i in.mp3 -ac 1 -ar 44100 orig.wav
"""
import argparse
from pathlib import Path

import numpy as np

from song import BAR, SHARP, Song, melody_wave, read_wav, write_wav

TEMPLATES = {f"{SHARP[r]}{q}": [(r + i) % 12 for i in iv] for r in range(12)
             for q, iv in (("", [0, 4, 7]), ("m", [0, 3, 7]), ("7", [0, 4, 7, 10]))}


def chroma(seg, sr):
    if len(seg) < 4096:
        return np.zeros(12)
    win = np.hanning(4096)
    frames = [seg[i:i + 4096] * win for i in range(0, len(seg) - 4096, 1024)] or [seg[:4096] * win]
    spec = np.abs(np.fft.rfft(np.array(frames), axis=1)).mean(0)
    freqs = np.fft.rfftfreq(4096, 1 / sr)
    band = (freqs > 65) & (freqs < 1000)  # 偏重伴奏的中低頻
    c = np.zeros(12)
    np.add.at(c, np.round(69 + 12 * np.log2(freqs[band] / 440)).astype(int) % 12, spec[band] ** 2)
    return c / (c.sum() + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("orig")
    ap.add_argument("--key", help="原錄音的調，省略＝譜面原調")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--offset", type=float, required=True, help="第一個字在錄音裡的秒數")
    ap.add_argument("--out")
    a = ap.parse_args()
    song = Song(a.song, a.key)
    out = Path(a.out) if a.out else song.path.parent
    y, sr = read_wav(a.orig)
    evs = song.events()
    sec16 = 60 / a.bpm / 4

    mel = melody_wave(evs, a.bpm, sr)
    pad = int(a.offset * sr)
    right = np.zeros(len(y))
    right[pad:pad + len(mel)] = mel[:max(0, len(y) - pad)]
    st = np.stack([y / np.abs(y).max(), right / (np.abs(right).max() + 1e-9)], 1) * 0.8
    write_wav(out / "對照試聽_左原唱_右手打譜.wav", st, sr)

    lines = []
    for bar in range(1, len(song.bars) + 1):
        for half in (0, 1):
            t0 = song.pickup_len + (bar - 1) * BAR + half * 8
            t1 = t0 + 8
            s, e = int((a.offset + t0 * sec16) * sr), int((a.offset + t1 * sec16) * sr)
            c = chroma(y[s:e], sr)
            mel_pc = np.zeros(12)
            for t, d, m, *_ in evs:
                if m is not None and t < t1 and t + d > t0:
                    mel_pc[m % 12] += min(t + d, t1) - max(t, t0)
            mel_pc /= mel_pc.sum() + 1e-9
            scores = {}
            for name, pcs in TEMPLATES.items():
                tpl = np.zeros(12)
                tpl[pcs] = 1 / len(pcs)
                scores[name] = 0.7 * float(c @ tpl) / (np.sqrt((c ** 2).sum() * (tpl ** 2).sum()) + 1e-9) + 0.3 * float(mel_pc[pcs].sum())
            best = sorted(scores, key=scores.get, reverse=True)[:3]
            words = "".join(ch for t, d, m, ch, py, first, b in evs if first and m is not None and t0 <= t < t1)
            lines.append(f"第{bar:2d}小節{'前後'[half]}半  {words:<6}  " + "  ".join(f"{n}({scores[n]:.2f})" for n in best))
    (out / f"和弦分析_原錄音_{song.key}調.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
