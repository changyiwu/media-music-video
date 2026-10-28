"""輕快流行編曲：照 song.json 的旋律與和弦產生多軌 GM 伴奏 MIDI 與 numpy 粗略預覽。旋律一個音都不改。

用法：python arrange.py <song.json> [--key C] [--bpm 128] [--intro-bars 4] [--tag 輕快版] [--out 資料夾]

結構（每小節 16 個十六分音符）：
- 前奏 N 小節：鐘琴＋銅管演奏最後 N 小節的旋律，和弦同那 N 小節
- 接一個過門小節：屬七和弦＋鼓過門，弱起的字唱在這小節最後
- 主歌（第 1 小節到 chorus_bar 前）：鼓輕、鋼琴反拍、吉他刷奏、貝斯根音
- 副歌（chorus_bar 到最後）：全團、Crash、貝斯跳五度；brass_hits 指定小節的旋律加銅管重音
- 尾奏：主和弦齊奏一小節
song.json 沒寫 arrange.chorus_bar 時整首當主歌。人聲 MIDI 用 score.py 同一個 --intro-bars 對齊。
輸出：伴奏_<tag>_<BPM>BPM.mid、_含旋律導引.mid（多一軌長笛奏旋律，試聽用）、伴奏預覽_*.wav（只聽結構，不是成品音質）
真樂器音色用 render.py（FluidSynth）把 MIDI 算成 wav。
"""
import argparse
import struct
from pathlib import Path

import numpy as np

from song import BAR, Song, tempo_meta, vlq, write_wav

PROGRAMS = {"bass": (0, 33), "piano": (1, 0), "guitar": (2, 27), "brass": (3, 61), "bells": (4, 9), "drums": (9, None),
            "guide": (5, 73)}  # (聲道, GM 音色)：指彈貝斯、平台鋼琴、清音電吉他、銅管組、鐘琴、鼓組（第 10 聲道）、長笛


class Arrangement:
    def __init__(self, song, intro):
        self.song, self.intro = song, intro
        self.nbars = len(song.bars)
        self.chorus = song.arrange.get("chorus_bar", self.nbars + 1)
        self.vocal_at = BAR * (intro + 1) - song.pickup_len  # 人聲第一個音的位置
        self.end = self.bar_start(self.nbars + 1) + BAR

    def bar_start(self, k):
        """譜面第 k 小節（1 起）在伴奏時間軸上的起點"""
        return (self.intro + k) * BAR

    def section(self, t):
        if t < self.intro * BAR:
            return "intro"
        if t < self.bar_start(self.chorus):
            return "verse"
        if t < self.bar_start(self.nbars + 1):
            return "chorus"
        return "outro"

    def chord_halves(self):
        """[(起點, 長度, 和弦名)]，涵蓋前奏、過門小節、全曲與尾奏"""
        song, out = self.song, []
        for b, (a, c) in enumerate(song.chart[-self.intro:] if self.intro else []):
            out += [(b * BAR, 8, a), (b * BAR + 8, 8, c or a)]
        out += [(self.intro * BAR, BAR, None)]  # 過門小節：屬七
        for k, (a, c) in enumerate(song.chart, start=1):
            s = self.bar_start(k)
            out += [(s, 8, a), (s + 8, 8, c or a)]
        out += [(self.bar_start(self.nbars + 1), BAR, "")]  # 尾奏：主和弦
        return out

    def pcs(self, name):
        song = self.song
        if name is None:
            return song.chord(song.dominant7())
        if name == "":
            return song.chord(song.tonic())
        return song.chord(name)

    def build(self):
        tr = {k: [] for k in ("drums", "bass", "piano", "guitar", "brass", "bells")}  # (起點, 長度, 音, 力度)

        def voicing(pcs, lo, hi):
            return sorted(m for m in range(lo, hi) if m % 12 in pcs)[:4]

        for s, d, name in self.chord_halves():
            sec = self.section(s)
            _, pcs, bass = self.pcs(name)
            bass_root = 36 + (bass - 36) % 12
            if sec == "outro":
                tr["bass"].append((s, 16, bass_root, 110))
                tr["piano"] += [(s, 16, m, 105) for m in voicing(pcs, 55, 72)]
                tr["guitar"] += [(s, 16, m, 100) for m in voicing(pcs, 52, 67)]
                tr["brass"] += [(s, 8, m, 110) for m in voicing(pcs, 60, 76)]
                continue
            fifth = bass_root + 7 if bass_root + 7 < 50 else bass_root - 5
            for i in range(0, d, 2):  # 貝斯八分音符；主歌以外每半小節最後一個八分跳五度
                note = fifth if (i == d - 2 and sec != "verse") else bass_root
                tr["bass"].append((s + i, 2, note, 100 if i % 4 == 0 else 85))
            if sec == "verse":  # 鋼琴：主歌反拍短和弦，其他每拍和弦
                for i in range(2, d, 4):
                    tr["piano"] += [(s + i, 1, m, 80) for m in voicing(pcs, 55, 72)]
            else:
                for i in range(0, d, 4):
                    tr["piano"] += [(s + i, 3, m, 92 if i % 8 == 4 else 84) for m in voicing(pcs, 55, 72)]
            for i, v in ((0, 90), (4, 70), (6, 80), (10, 72), (12, 80), (14, 70)):  # 吉他刷奏
                if i < d:
                    tr["guitar"] += [(s + i, 2, m, v - (12 if sec == "verse" else 0)) for m in voicing(pcs, 52, 67)]

        # 鼓（GM：36 大鼓、38 小鼓、42 閉合鈸、46 開放鈸、49 Crash、45/47/50 筒鼓）
        D = tr["drums"]
        fills = {self.intro - 1, self.intro, self.intro + self.chorus - 1, self.intro + self.nbars}  # 前奏尾、過門小節、進副歌前、尾奏前
        crashes = {0, self.intro + 1, self.intro + self.chorus}
        for bar in range(self.end // BAR):
            s = bar * BAR
            sec = self.section(s)
            if sec == "outro":
                D += [(s, 8, 49, 120), (s, 4, 36, 120)]
                break
            fill = bar in fills
            if bar in crashes:
                D.append((s, 8, 49, 115))
            for i in range(0, 16, 2):
                if fill and i >= 8:
                    break
                D.append((s + i, 1, 46 if (sec == "chorus" and i % 8 == 6) else 42, 70 if i % 4 else 85))
            for i in (0, 6, 8) if sec != "verse" else (0, 8):
                D.append((s + i, 2, 36, 110))
            for i in (4, 12):
                if not (fill and i == 12):
                    D.append((s + i, 2, 38, 100 if sec == "verse" else 112))
            if fill:
                for j, n in enumerate((50, 50, 47, 47, 45, 45, 38, 38)):
                    D.append((s + 8 + j, 1, n, 90 + j * 3))

        # 前奏旋律（最後 N 小節）由鐘琴＋銅管演奏；brass_hits 小節銅管重音
        hits = set(self.song.arrange.get("brass_hits", []))
        phrase_start = self.song.pickup_len + BAR * (self.nbars - self.intro)
        for t, d, m, ch, py, first, bar_no in self.song.events():
            if m is None:
                continue
            if self.intro and bar_no > self.nbars - self.intro:
                tt = t - phrase_start
                tr["bells"].append((tt, d, m + 12, 100))
                tr["brass"].append((tt, d, m, 95))
            if bar_no in hits:
                tr["brass"].append((self.vocal_at + t, d, m, 115))
        return tr

    def guide(self, octave=0):
        return [(self.vocal_at + t, d, m + octave, 100) for t, d, m, *_ in self.song.events() if m is not None]


def write_midi(path, tr, bpm):
    tpq, tick = 480, 120
    chunks = [bytes(tempo_meta(bpm) + vlq(0) + b"\xff\x2f\x00")]
    for name, notes in tr.items():
        ch, prog = PROGRAMS[name]
        evs = []
        for s, d, m, v in notes:
            evs.append((s * tick, 1, bytes([0x90 | ch, m, v])))
            evs.append(((s + d) * tick - 1, 0, bytes([0x80 | ch, m, 0])))
        evs.sort(key=lambda e: (e[0], e[1]))
        nm = name.encode()
        body = bytearray(vlq(0) + b"\xff\x03" + vlq(len(nm)) + nm)
        if prog is not None:
            body += vlq(0) + bytes([0xC0 | ch, prog])
        now = 0
        for t, _, msg in evs:
            body += vlq(t - now) + msg
            now = t
        body += vlq(0) + b"\xff\x2f\x00"
        chunks.append(bytes(body))
    data = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), tpq)
    for c in chunks:
        data += b"MTrk" + struct.pack(">I", len(c)) + c
    Path(path).write_bytes(data)


def render(tr, end, bpm, guide=None, sr=44100):
    """粗略預覽：numpy 合成的簡單音色，只用來聽編曲結構"""
    sec16 = 60 / bpm / 4
    total = int((end + 8) * sec16 * sr)
    out = np.zeros((total, 2))
    rng = np.random.default_rng(0)
    pan = {"bass": 0.5, "piano": 0.35, "guitar": 0.7, "brass": 0.45, "bells": 0.6, "drums": 0.5, "guide": 0.5}
    gain = {"bass": 0.55, "piano": 0.16, "guitar": 0.09, "brass": 0.12, "bells": 0.18, "drums": 0.5, "guide": 0.32}

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def synth(kind, m, n, v):
        t = np.arange(n) / sr
        a = v / 127
        if kind == "bass":
            f = hz(m)
            return a * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 3) * np.minimum(1, t / 0.005)
        if kind in ("piano", "guide"):
            f = hz(m)
            s = sum(k * np.sin(2 * np.pi * f * h * t) for h, k in ((1, 1), (2, 0.4), (3, 0.2), (4, 0.1)))
            return a * s * np.exp(-t * (2.5 if kind == "piano" else 1.2)) * np.minimum(1, t / 0.004)
        if kind == "guitar":
            f = hz(m)
            return a * sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 7)) * np.exp(-t * 6) * np.minimum(1, t / 0.002)
        if kind == "brass":
            f = hz(m)
            return a * sum(np.sin(2 * np.pi * f * h * t) / h ** 0.8 for h in range(1, 8)) * np.minimum(1, t / 0.03) * np.exp(-t * 1.5)
        if kind == "bells":
            f = hz(m)
            return a * (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t * 3.5)
        if m == 36:
            f = 50 + 90 * np.exp(-t * 30)
            return a * 1.6 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 9)
        if m == 38:
            return a * (0.7 * rng.standard_normal(n) * np.exp(-t * 18) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25))
        if m in (42, 46, 49):
            noise = np.diff(np.concatenate([[0], rng.standard_normal(n)]))  # 粗略高通
            return a * 0.35 * noise * np.exp(-t * {42: 40, 46: 9, 49: 3}[m])
        f = {45: 110, 47: 140, 50: 180}.get(m, 150)
        return a * np.sin(2 * np.pi * f * (1 + 0.5 * np.exp(-t * 20)) * t) * np.exp(-t * 10)

    parts = dict(tr)
    if guide:
        parts["guide"] = guide
    for name, notes in parts.items():
        p = pan[name]
        for s, d, m, v in notes:
            n = int((d if name != "drums" else max(d, 4)) * sec16 * sr) + int(0.08 * sr)
            st = int(s * sec16 * sr)
            n = min(n, total - st)
            x = synth(name, m, n, v) * gain[name]
            out[st:st + n, 0] += x * (1 - p) * 2 ** 0.5
            out[st:st + n, 1] += x * p * 2 ** 0.5
    return np.tanh(out / np.abs(out).max() * 1.2) * 0.85


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--key")
    ap.add_argument("--bpm", type=float, default=128)
    ap.add_argument("--intro-bars", type=int, default=4)
    ap.add_argument("--tag", default="輕快版")
    ap.add_argument("--out")
    a = ap.parse_args()
    song = Song(a.song, a.key)
    out = Path(a.out) if a.out else song.path.parent
    arr = Arrangement(song, a.intro_bars)
    tr = arr.build()
    name = f"{a.tag}_{a.bpm:g}BPM"
    write_midi(out / f"伴奏_{name}.mid", tr, a.bpm)
    write_midi(out / f"伴奏_{name}_含旋律導引.mid", {**tr, "guide": arr.guide(12)}, a.bpm)
    y = render(tr, arr.end, a.bpm, guide=arr.guide())
    write_wav(out / f"伴奏預覽_{name}_含旋律導引.wav", y)
    write_wav(out / f"伴奏預覽_{name}_純伴奏.wav", render(tr, arr.end, a.bpm))
    print(f"伴奏 {arr.end // BAR} 小節、{len(y) / 44100:.1f} 秒；人聲第一個字在 {arr.vocal_at * 15 / a.bpm:.2f} 秒"
          f"（人聲 MIDI：score.py --bpm {a.bpm:g} --intro-bars {a.intro_bars}）")


if __name__ == "__main__":
    main()
