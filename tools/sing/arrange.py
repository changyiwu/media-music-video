"""編曲（輕快流行樂團／管弦樂進行曲／搖滾）：照 song.json 的旋律與和弦產生多軌 GM 伴奏 MIDI 與 numpy 粗略預覽。旋律一個音都不改。

用法：python arrange.py <song.json> [--key C] [--bpm 128] [--intro-bars 4] [--style band|march|rock] [--tag 輕快版] [--out 資料夾]

結構（每小節 16 個十六分音符）：
- 前奏 N 小節：鐘琴＋銅管演奏最後 N 小節的旋律，和弦同那 N 小節
- 接一個過門小節：屬七和弦＋鼓過門，弱起的字唱在這小節最後
- 主歌（第 1 小節到 chorus_bar 前）：鼓輕、鋼琴反拍、吉他刷奏、貝斯根音
- 副歌（chorus_bar 到最後）：全團、Crash、貝斯跳五度；brass_hits 指定小節的旋律加銅管重音
- 尾奏：主和弦齊奏一小節
song.json 沒寫 arrange.chorus_bar 時整首當主歌。人聲 MIDI 用 score.py 同一個 --intro-bars 對齊。
--style march：管弦樂進行曲、--style rock：搖滾（見 March、Rock 類別說明），都配 MuseScore General 音色庫算（render.py --sf MuseScore_General）
輸出：伴奏_<tag>_<BPM>BPM.mid、_含旋律導引.mid（多一軌長笛奏旋律，試聽用）、伴奏預覽_*.wav（band 才有，只聽結構，不是成品音質）
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


MARCH_PROGRAMS = {"strings": (0, 48), "cello": (1, 42), "pizz": (2, 45), "flute": (3, 73), "clarinet": (4, 71),
                  "horn": (5, 60), "trumpet": (6, 56), "trombone": (7, 57), "drums": (9, None), "tuba": (10, 58),
                  "timpani": (11, 47), "glock": (12, 9), "harp": (13, 46), "guide": (14, 73)}
MARCH_VOLUME = {"strings": 100, "cello": 92, "pizz": 88, "flute": 78, "clarinet": 82, "horn": 92, "trumpet": 96,
                "trombone": 86, "drums": 92, "tuba": 96, "timpani": 100, "glock": 72, "harp": 88, "guide": 90}


class March(Arrangement):
    """管弦樂進行曲：低音（大號＋撥弦）打一、三拍，法國號（副歌加長號）打二、四拍的「嗯—趴」；
    弦樂鋪和弦、單簧管（主歌）／小提琴（副歌）吹和弦內音連成的對位線，副歌長笛高八度疊旋律；
    小鼓進行曲節奏、大鼓＋鈸、定音鼓；前奏小號＋鐘琴奏最後一句，進副歌前豎琴琶音；尾奏全團主和弦＋定音鼓滾奏。
    力度加隨機微調、起音略晚 0～10ms，弦樂用 CC11 做漸強漸弱。算圖：render.py --sf MuseScore_General --hall --gain 0.45"""
    programs, volume = MARCH_PROGRAMS, MARCH_VOLUME

    def build(self):
        rng = np.random.default_rng(1)
        tr = {k: [] for k in MARCH_PROGRAMS if k != "guide"}
        cc = {"strings": [], "cello": []}

        def add(part, s, d, m, v, human=True):
            if human:
                s += rng.uniform(0, 0.08)
                v += int(rng.integers(-5, 6))
            tr[part].append((s, d, m, int(np.clip(v, 1, 127))))

        def voicing(pcs, lo, hi, n=4):
            return sorted(m for m in range(lo, hi) if m % 12 in pcs)[:n]

        def nearest(pcs, prev, lo, hi, prefer):
            cands = [m for m in range(lo, hi) if m % 12 in pcs]
            good = [m for m in cands if m % 12 in prefer] or cands
            return min(good, key=lambda m: abs(m - prev))

        def roll(part, s, d, m, v0, v1):
            n = int(d * 2)  # 三十二分音符
            for i in range(n):
                add(part, s + i / 2, 0.5, m, int(v0 + (v1 - v0) * i / max(1, n - 1)), human=False)

        halves = self.chord_halves()
        line_w, line_v = 62, 74  # 對位線上一個音（單簧管、小提琴）
        for idx, (s, d, name) in enumerate(halves):
            sec = self.section(s)
            _, pcs, bass = self.pcs(name)
            third = {pcs[1]} | ({pcs[3]} if len(pcs) > 3 else set())
            root = 36 + (bass - 36) % 12
            loud = sec in ("chorus", "intro")
            if sec == "outro":
                for part, lo, hi, v in (("strings", 55, 84, 110), ("horn", 53, 67, 105), ("trombone", 48, 62, 105),
                                        ("trumpet", 60, 76, 110), ("flute", 72, 88, 95), ("clarinet", 60, 72, 95)):
                    for m in voicing(pcs, lo, hi):
                        add(part, s, 16, m, v)
                add("cello", s, 16, root + 12, 105)
                add("tuba", s, 16, root, 110)
                add("harp", s, 16, root + 24, 100)
                continue
            # 弦樂鋪底：每半小節一個和弦（同和弦連起來不重打），主歌輕、副歌厚
            prev = halves[idx - 1][2] if idx else "?"
            if name != prev or s % BAR == 0:
                nxt = halves[idx + 1] if idx + 1 < len(halves) else None
                dd = 16 if (d == 8 and s % BAR == 0 and nxt and nxt[2] == name) else d
                for m in voicing(pcs, 55 if loud else 60, 76 if loud else 74, 4 if loud else 3):
                    add("strings", s, dd, m, 82 if loud else 72)
                add("cello", s, dd, root + 12, 80 if loud else 70)
            # 對位線：取三音／七音、離上一個音最近
            if sec == "verse":
                line_w = nearest(pcs, line_w, 55, 70, third)
                add("clarinet", s, 8, line_w, 74)
            elif sec == "chorus":
                line_v = nearest(pcs, line_v, 67, 82, third)
                add("strings", s, 8, line_v, 88)
            # 嗯—趴
            fifth = root + 7 if root + 7 < 48 else root - 5
            add("tuba", s, 3, root if s % BAR == 0 or d == BAR else fifth, 92 if loud else 80)
            if sec != "intro" and d < BAR:
                add("pizz", s, 2, root + 12, 85 if loud else 78)
            for off in (4,) if d < BAR else (4, 12):
                for m in voicing(pcs, 53, 66, 3):
                    add("horn", s + off, 2, m, 82 if loud else 70)
                if loud:
                    for m in voicing(pcs, 48, 60, 2):
                        add("trombone", s + off, 2, m, 78)
            if d == BAR:  # 過門小節多打一個「嗯」
                add("tuba", s + 8, 3, fifth, 88)

        # 弦樂表情：主歌 92、副歌 112；進副歌前一小節漸強
        for part in cc:
            for bar in range(self.end // BAR):
                s, sec = bar * BAR, self.section(bar * BAR)
                base = {"intro": 105, "verse": 92, "chorus": 112, "outro": 115}[sec]
                if bar == self.intro + self.chorus - 1:
                    cc[part] += [(s + i, 11, int(92 + (115 - 92) * i / 15)) for i in range(16)]
                elif bar == self.intro:
                    cc[part] += [(s + i, 11, int(95 + 20 * i / 15)) for i in range(16)]
                else:
                    cc[part].append((s, 11, base))

        # 打擊：小鼓（38）、大鼓（36）、鈸（49）、定音鼓
        fills = {self.intro - 1, self.intro + self.chorus - 1, self.intro + self.nbars}
        for bar in range(self.end // BAR):
            s, sec = bar * BAR, self.section(bar * BAR)
            _, pcs, bass = self.pcs(next(n for t, d, n in self.chord_halves() if t <= s < t + d))
            timp = 41 + (bass - 41) % 12
            if sec == "outro":
                roll("timpani", s, 12, timp, 70, 115)
                add("timpani", s + 12, 4, timp, 120)
                roll("drums", s, 12, 38, 50, 110)
                add("drums", s + 12, 4, 49, 120)
                add("drums", s + 12, 4, 36, 120)
                break
            if bar == self.intro:  # 過門小節：小鼓、定音鼓滾奏漸強，留第四拍給人聲弱起
                roll("drums", s, 12, 38, 45, 105)
                roll("timpani", s, 12, timp, 50, 100)
                continue
            if sec == "verse":
                pattern = ((4, 62), (12, 62), (14, 50), (15, 54))
            else:
                pattern = ((0, 100), (4, 88), (6, 66), (7, 70), (8, 96), (12, 88), (14, 72), (15, 78))
            if bar in fills:
                pattern = tuple(p for p in pattern if p[0] < 8)
                roll("drums", s + 8, 8, 38, 60, 112)
            for i, v in pattern:
                add("drums", s + i, 1, 38, v)
            add("drums", s, 2, 36, 96 if sec != "verse" else 78)
            if sec != "verse":
                add("drums", s + 8, 2, 36, 88)
                add("drums", s, 4, 49, 78 if bar % 2 else 92)
                add("timpani", s, 2, timp, 92)
            if bar in (0, self.intro + 1, self.intro + self.chorus):
                add("drums", s, 8, 49, 118)
                add("timpani", s, 4, timp, 110)

        # 豎琴：進副歌前的半小節由低到高琶音
        s0 = self.bar_start(self.chorus) - 8
        _, pcs, _ = self.pcs(next(n for t, d, n in halves if t <= s0 < t + d))
        notes = [m for m in range(48, 96) if m % 12 in pcs]
        for i, m in enumerate(notes[:16]):
            add("harp", s0 + i * 0.5, 8 - i * 0.5, m, 70 + i * 2, human=False)

        # 旋律：前奏小號＋鐘琴奏最後幾小節；副歌長笛高八度；brass_hits 小號＋長號重音
        hits = set(self.song.arrange.get("brass_hits", []))
        phrase_start = self.song.pickup_len + BAR * (self.nbars - self.intro)
        for t, d, m, ch, py, first, bar_no in self.song.events():
            if m is None:
                continue
            if self.intro and bar_no > self.nbars - self.intro:
                tt = t - phrase_start
                add("trumpet", tt, d, m, 100)
                add("glock", tt, d, m + 24, 90)
                add("flute", tt, d, m + 12, 80)
            at = self.vocal_at + t
            if self.section(at) == "chorus":
                add("flute", at, d, m + 12, 72)
            if bar_no in hits:
                add("trumpet", at, d, m, 110)
                add("trombone", at, d, m - 12, 100)
        return tr, cc


ROCK_PROGRAMS = {"gtr_l": (0, 30), "gtr_r": (1, 29), "lead": (2, 30), "bass": (3, 34), "piano": (4, 0),
                 "strings": (5, 48), "drums": (9, None), "guide": (6, 73)}  # 破音吉他×2（左右）、主奏吉他、彈片貝斯、鋼琴、弦樂
ROCK_VOLUME = {"gtr_l": 112, "gtr_r": 112, "lead": 118, "bass": 104, "piano": 72, "strings": 68, "drums": 100, "guide": 90}
# 2026-10-28 使用者要求電吉他加強：吉他 82→112、主奏 90→118，鋼琴、弦樂讓位
ROCK_PAN = {"gtr_l": 22, "gtr_r": 106, "lead": 64, "bass": 64, "piano": 50, "strings": 78, "drums": 64, "guide": 64}


class Rock(Arrangement):
    """搖滾：主歌左聲道破音吉他悶音八分音符＋鋼琴，副歌左右兩把吉他強力和弦（根音＋五度＋八度）、弦樂鋪底、
    鼓改開放鈸／Crash、大鼓加密；前奏與 brass_hits 小節由主奏吉他奏旋律；尾奏強力和弦延長＋鼓收尾。
    強力和弦不分大小調，只彈根音與五度，避免破音和弦糊掉。算圖：render.py --sf MuseScore_General --gain 0.5"""
    programs, volume = ROCK_PROGRAMS, ROCK_VOLUME

    def build(self):
        rng = np.random.default_rng(2)
        tr = {k: [] for k in ROCK_PROGRAMS if k != "guide"}
        cc = {k: [(0, 10, ROCK_PAN[k])] for k in ROCK_PROGRAMS}

        def add(part, s, d, m, v, human=True):
            if human:
                s += rng.uniform(0, 0.06)
                v += int(rng.integers(-5, 6))
            tr[part].append((s, d, m, int(np.clip(v, 1, 127))))

        def power(pc, lo=40):
            r = lo + (pc - lo) % 12
            return [r, r + 7, r + 12]

        for s, d, name in self.chord_halves():
            sec = self.section(s)
            _, pcs, bass = self.pcs(name)
            root = 28 + (bass - 28) % 12  # 貝斯 E1～D#2
            pw = power(bass)
            if sec == "outro":
                for m in pw:
                    add("gtr_l", s, 16, m, 112)
                    add("gtr_r", s, 16, m, 112)
                add("bass", s, 16, root, 115)
                add("strings", s, 16, pw[-1] + 12, 100)
                continue
            for i in range(0, d, 2):  # 貝斯八分音符
                add("bass", s + i, 1.8, root, 100 if i % 4 == 0 else 86)
            if sec == "verse":  # 主歌：左吉他悶音八分、鋼琴每拍和弦
                for i in range(0, d, 2):
                    for m in pw[:2]:
                        add("gtr_l", s + i, 1.2, m, 84 if i % 4 == 0 else 72)
                for i in range(0, d, 4):
                    for m in sorted(x for x in range(55, 72) if x % 12 in pcs)[:3]:
                        add("piano", s + i, 3, m, 70)
            else:  # 前奏、過門、副歌：兩把吉他長音強力和弦＋右吉他八分推進
                for m in pw:
                    add("gtr_l", s, d - 0.3, m, 104)
                for i in range(0, d, 2):
                    for m in pw[:2]:
                        add("gtr_r", s + i, 1.4, m, 96 if i % 4 == 0 else 84)
                for m in sorted(x for x in range(60, 80) if x % 12 in pcs)[:3]:
                    add("strings", s, d, m, 84)

        D = tr["drums"]
        fills = {self.intro - 1, self.intro, self.intro + self.chorus - 1, self.intro + self.nbars}
        crashes = {0, self.intro + 1, self.intro + self.chorus}
        for bar in range(self.end // BAR):
            s, sec = bar * BAR, self.section(bar * BAR)
            if sec == "outro":
                D += [(s, 8, 49, 124), (s, 8, 57, 118), (s, 4, 36, 124)]
                break
            fill = bar in fills
            if bar in crashes or (sec == "chorus" and bar % 4 == (self.intro + self.chorus) % 4):
                add("drums", s, 8, 49, 118)
            cym = 42 if sec == "verse" else 46  # 主歌閉合鈸、副歌開放鈸
            for i in range(0, 16, 2):
                if fill and i >= 8:
                    break
                add("drums", s + i, 1, cym, 82 if i % 4 == 0 else 66)
            kicks = (0, 8, 10) if sec == "verse" else (0, 3, 6, 8, 10, 14)
            for i in kicks:
                if not (fill and i >= 8):
                    add("drums", s + i, 2, 36, 112)
            for i in (4, 12):
                if not (fill and i == 12):
                    add("drums", s + i, 2, 38, 108 if sec == "verse" else 120)
            if fill:  # 筒鼓過門
                for j, n in enumerate((50, 50, 48, 48, 47, 47, 45, 45)):
                    add("drums", s + 8 + j, 1, n, 96 + j * 3)
                add("drums", s + 15, 1, 38, 120)

        # 主奏吉他：前奏奏最後幾小節旋律、brass_hits 小節疊旋律（低八度，避開人聲音域）
        hits = set(self.song.arrange.get("brass_hits", []))
        phrase_start = self.song.pickup_len + BAR * (self.nbars - self.intro)
        for t, d, m, ch, py, first, bar_no in self.song.events():
            if m is None:
                continue
            if self.intro and bar_no > self.nbars - self.intro:
                add("lead", t - phrase_start, d, m, 108)
            if bar_no in hits:
                add("lead", self.vocal_at + t, d, m - 12, 100)
        return tr, cc


def write_midi(path, tr, bpm, programs=PROGRAMS, cc=None, volume=None):
    """tr：{軌名: [(起點, 長度, 音, 力度)]}，位置以十六分音符計（可為小數）；
    cc：{軌名: [(位置, 控制器號, 值)]}（例如 11 表情）；volume：{軌名: CC7 音量}"""
    tpq, tick = 480, 120
    chunks = [bytes(tempo_meta(bpm) + vlq(0) + b"\xff\x2f\x00")]
    for name, notes in tr.items():
        ch, prog = programs[name]
        evs = []
        for s, d, m, v in notes:
            evs.append((round(s * tick), 2 if cc else 1, bytes([0x90 | ch, m, v])))
            evs.append((round((s + d) * tick) - 1, 0, bytes([0x80 | ch, m, 0])))
        for s, num, val in (cc or {}).get(name, []):
            evs.append((round(s * tick), 1, bytes([0xB0 | ch, num, val])))
        evs.sort(key=lambda e: (e[0], e[1]))
        nm = name.encode()
        body = bytearray(vlq(0) + b"\xff\x03" + vlq(len(nm)) + nm)
        if prog is not None:
            body += vlq(0) + bytes([0xC0 | ch, prog])
        if volume and name in volume:
            body += vlq(0) + bytes([0xB0 | ch, 7, volume[name]])
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
    ap.add_argument("--style", choices=["band", "march", "rock"], default="band", help="band：輕快流行樂團；march：管弦樂進行曲；rock：搖滾")
    ap.add_argument("--tag", help="檔名標籤，預設 band＝輕快版、march＝管弦進行曲版")
    ap.add_argument("--out")
    a = ap.parse_args()
    song = Song(a.song, a.key)
    out = Path(a.out) if a.out else song.path.parent
    name = f"{a.tag or {'band': '輕快版', 'march': '管弦進行曲版', 'rock': '搖滾版'}[a.style]}_{a.bpm:g}BPM"
    if a.style in ("march", "rock"):
        arr = (March if a.style == "march" else Rock)(song, a.intro_bars)
        tr, cc = arr.build()
        write_midi(out / f"伴奏_{name}.mid", tr, a.bpm, arr.programs, cc, arr.volume)
        write_midi(out / f"伴奏_{name}_含旋律導引.mid", {**tr, "guide": arr.guide(12)}, a.bpm, arr.programs, cc, arr.volume)
        sec = arr.end * 15 / a.bpm  # 管弦樂、搖滾的 numpy 預覽沒有參考價值，直接用 render.py 算
    else:
        arr = Arrangement(song, a.intro_bars)
        tr = arr.build()
        write_midi(out / f"伴奏_{name}.mid", tr, a.bpm)
        write_midi(out / f"伴奏_{name}_含旋律導引.mid", {**tr, "guide": arr.guide(12)}, a.bpm)
        y = render(tr, arr.end, a.bpm, guide=arr.guide())
        write_wav(out / f"伴奏預覽_{name}_含旋律導引.wav", y)
        write_wav(out / f"伴奏預覽_{name}_純伴奏.wav", render(tr, arr.end, a.bpm))
        sec = len(y) / 44100
    print(f"伴奏_{name}.mid：{arr.end // BAR} 小節、{sec:.1f} 秒；人聲第一個字在 {arr.vocal_at * 15 / a.bpm:.2f} 秒"
          f"（人聲 MIDI：score.py --bpm {a.bpm:g} --intro-bars {a.intro_bars}）")

if __name__ == "__main__":
    main()
