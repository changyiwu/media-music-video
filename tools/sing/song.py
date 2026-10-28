"""照譜唱歌曲工具的共用程式：讀譜面資料檔（song.json）、移調、和弦、MIDI／WAV 寫檔。

只用標準函式庫＋numpy（專案規則：不依賴 scipy）。其他腳本都 import 這支。

song.json 格式（長度單位一律是十六分音符；目前只支援 4/4）：
{
  "title": "曲名",  "stem": "旋律",           # stem：輸出檔名開頭，省略時用「旋律」
  "lyricist": "作詞",  "composer": "作曲",
  "key": "D",                                  # 譜面寫的調（大調），音名照譜面記
  "pickup": [["字", "pin1", [["D4", 3]]], ...],  # 弱起小節；沒有就給 []
  "bars":   [[["字", "pin1", [["A4", 8]]], ["", "", [["r", 4]]], ...], ...],
            # 每個字：[漢字, 帶調拼音（台灣讀音，輕聲 5）, [[音名, 長度], ...]]；一字多音就列多個音；休止 ["", "", [["r", 長度]]]
  "chords": [["D", "Bm"], ...],                # 每小節前後半各一個和弦（譜面調）；null＝延續前半
  "arrange": {"chorus_bar": 13, "brass_hits": [17]}  # 副歌從第幾小節開始、哪些小節的旋律加銅管重音
}
"""
import json
import struct
import wave
from pathlib import Path

import numpy as np

STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "Gb": -6, "Db": -5, "Ab": -4, "Eb": -3, "Bb": -2, "F": -1}
QUALITY = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11],
           "dim": [0, 3, 6], "aug": [0, 4, 8], "sus4": [0, 5, 7], "sus2": [0, 2, 7], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9]}
TONE_MARKS = {"a": "āáǎà", "e": "ēéěè", "i": "īíǐì", "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ"}
BAR = 16


def pc_of(name):
    """音名（不含八度）→ 0～11"""
    return (STEP[name[0]] + name[1:].count("#") - name[1:].count("b")) % 12


def midi_of(name, shift=0):
    """D4、F#4、Bb3 → MIDI 音高"""
    return 12 * (int(name[-1]) + 1) + STEP[name[0]] + name[1:-1].count("#") - name[1:-1].count("b") + shift


def key_shift(src, dst):
    """src 調移到 dst 調的半音數，取 -6～+5 的最近方向"""
    return (pc_of(dst) - pc_of(src) + 6) % 12 - 6


class Song:
    def __init__(self, path, key=None):
        self.path = Path(path)
        d = json.loads(self.path.read_text(encoding="utf-8"))
        self.d = d
        self.title, self.stem = d["title"], d.get("stem", "旋律")
        self.lyricist, self.composer = d.get("lyricist", ""), d.get("composer", "")
        self.key = key or d["key"]
        self.shift = key_shift(d["key"], self.key)
        self.fifths = FIFTHS[self.key]
        self.pickup, self.bars = d.get("pickup", []), d["bars"]
        self.pickup_len = sum(n[1] for w in self.pickup for n in w[2])
        self.chart = d.get("chords", [])
        self.arrange = d.get("arrange", {})

    def events(self):
        """攤平成音符清單：(起點, 長度, midi 或 None, 漢字, 拼音, 是否為字的第一個音, 小節號)；小節號 0＝弱起"""
        out, t = [], 0
        for bar_no, bar in enumerate([self.pickup] + self.bars):
            if bar_no == 0 and not bar:
                continue
            total = sum(d for _, _, ns in bar for _, d in ns)
            assert bar_no in (0, len(self.bars)) or total == BAR, f"第 {bar_no} 小節長度 {total}，應為 {BAR}"
            for char, py, notes in bar:
                for k, (n, d) in enumerate(notes):
                    out.append((t, d, None if n == "r" else midi_of(n, self.shift), char, py, k == 0, bar_no))
                    t += d
        return out

    def length16(self):
        e = self.events()[-1]
        return e[0] + e[1]

    def chord(self, name):
        """和弦名（譜面調）→ (顯示名, 組成音 pc，第一個是根音, 低音 pc)。支援 C、Am、G7、Fmaj7、Bdim、Csus4、C/E 等"""
        main, _, bass = name.partition("/")
        root = main[:2] if main[1:2] in ("#", "b") else main[:1]
        q = main[len(root):]
        r = (pc_of(root) + self.shift) % 12
        names = FLAT if self.fifths < 0 else SHARP
        pcs = [(r + i) % 12 for i in QUALITY[q]]
        b = (pc_of(bass) + self.shift) % 12 if bass else r
        return names[r] + q + (f"/{names[b]}" if bass else ""), pcs, b

    def halves(self):
        """[(小節號 1 起, 前半或後半 0/1, 和弦名或 None)]，null 延續同小節前半"""
        out = []
        for i, (a, b) in enumerate(self.chart, start=1):
            out += [(i, 0, a), (i, 1, b or a)]
        return out

    def dominant7(self):
        """屬七和弦名（譜面調，交給 chord() 再移調）"""
        names = FLAT if FIFTHS[self.d["key"]] < 0 else SHARP
        return names[(pc_of(self.d["key"]) + 7) % 12] + "7"

    def tonic(self):
        return self.d["key"]


def tone_mark(p):
    """wu2 → wú（a、e 優先，ou 標 o，其餘標最後一個母音；輕聲 5 不標）"""
    base, tone = p[:-1].replace("v", "ü"), int(p[-1])
    if tone == 5:
        return base
    for v in ("a", "e"):
        if v in base:
            return base.replace(v, TONE_MARKS[v][tone - 1], 1)
    if "ou" in base:
        return base.replace("o", TONE_MARKS["o"][tone - 1], 1)
    i = max(base.rfind(v) for v in "iouü")
    return base[:i] + TONE_MARKS[base[i]][tone - 1] + base[i + 1:]


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def tempo_meta(bpm):
    return vlq(0) + b"\xff\x51\x03" + struct.pack(">I", round(60_000_000 / bpm))[1:] + vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08"


def write_wav(path, y, sr=44100):
    """y：-1～1 的 float，單聲道一維或 (n, 2)"""
    y = np.asarray(y)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1 if y.ndim == 1 else y.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def read_wav(path, stereo=False):
    """回傳 (float 陣列, 取樣率)；stereo=True 時一律 (n, 2)，否則混成單聲道"""
    with wave.open(str(path)) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        y = np.frombuffer(w.readframes(n), dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float64)
    y = y.reshape(-1, ch) / (2 ** (8 * sw - 1))
    if stereo:
        return (np.repeat(y, 2, axis=1) if ch == 1 else y[:, :2]), sr
    return y.mean(1), sr


def melody_wave(evs, bpm, sr=44100, offset16=0):
    """旋律試聽：加泛音的簡單音色，只用來核對音高與節奏（未正規化）"""
    sec16 = 60 / bpm / 4
    total = int((evs[-1][0] + evs[-1][1] + offset16) * sec16 * sr) + sr
    y = np.zeros(total)
    for t, d, m, *_ in evs:
        if m is None:
            continue
        n = int(d * sec16 * sr)
        tt = np.arange(n) / sr
        f = 440 * 2 ** ((m - 69) / 12)
        tone = sum(a * np.sin(2 * np.pi * f * h * tt) for h, a in ((1, 1.0), (2, 0.35), (3, 0.15)))
        env = np.minimum(1, tt / 0.01) * np.exp(-tt * 1.8) * np.minimum(1, (n / sr - tt) / 0.03)
        s = int((t + offset16) * sec16 * sr)
        y[s:s + n] += tone * env
    return y
