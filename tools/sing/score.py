"""照譜面資料（song.json）輸出 MusicXML、歌聲合成用 MIDI 與旋律試聽 wav。

用法：python score.py <song.json> [--key C] [--bpm 110] [--intro-bars 4] [--out 資料夾]
- --key：輸出的調（大調），省略＝譜面原調；例如原錄音比譜低一個全音就給 --key C
- 輸出（預設放 song.json 旁邊，檔名 <stem>_<調>調_<BPM>BPM）：
  .musicxml（第一行漢字、第二行帶調拼音；一字多音用圓滑線＋延長線）
  _漢字.mid、_拼音.mid（lyric 事件，一字多音的後續音標 "-"，給 Synthesizer V 等）
  _OpenUtau.mid（拼音、延續記號 "+"，OpenUtau 的規定）、_試聽.wav
- --intro-bars N：只輸出 _OpenUtau.mid，人聲前面多空 N 小節，配合 arrange.py 的前奏
- MIDI 前面先空到弱起落在第 1 小節的對應拍上，小節線跟譜面（及伴奏）對齊
"""
import argparse
import struct
from pathlib import Path

import numpy as np

from song import BAR, Song, tempo_meta, tone_mark, vlq, write_wav, melody_wave

STEPS = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"]
ALTERS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
TYPES = {1: ("16th", 0), 2: ("eighth", 0), 3: ("eighth", 1), 4: ("quarter", 0), 6: ("quarter", 1),
         8: ("half", 0), 12: ("half", 1), 16: ("whole", 0)}


def write_musicxml(path, song, evs, bpm):
    x = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
         '<score-partwise version="4.0">',
         f'<work><work-title>{song.title}</work-title></work>',
         f'<identification><creator type="lyricist">{song.lyricist}</creator><creator type="composer">{song.composer}</creator></identification>',
         '<part-list><score-part id="P1"><part-name>Vocal</part-name></score-part></part-list>', '<part id="P1">']
    by_bar = {}
    for e in evs:
        by_bar.setdefault(e[6], []).append(e)
    first_bar = min(by_bar)
    for b in sorted(by_bar):
        attrs = ' implicit="yes"' if b == 0 else ""
        x.append(f'<measure number="{b}"{attrs}>')
        if b == first_bar:
            x.append(f'<attributes><divisions>4</divisions><key><fifths>{song.fifths}</fifths></key>'
                     '<time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>')
            x.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                     f'<per-minute>{bpm:g}</per-minute></metronome></direction-type><sound tempo="{bpm:g}"/></direction>')
        notes = by_bar[b]
        for i, (t, d, m, char, py, first, _) in enumerate(notes):
            typ, dots = TYPES[d]
            dot = "<dot/>" * dots
            if m is None:
                x.append(f"<note><rest/><duration>{d}</duration><type>{typ}</type>{dot}</note>")
                continue
            same_char_next = i + 1 < len(notes) and not notes[i + 1][5] and notes[i + 1][3] == char
            notations = ""
            if same_char_next and first:
                notations = '<notations><slur type="start"/></notations>'
            elif not first and not same_char_next:
                notations = '<notations><slur type="stop"/></notations>'
            lyric = ""
            if first:
                ext = "<extend/>" if same_char_next else ""
                lyric = (f'<lyric number="1"><syllabic>single</syllabic><text>{char}</text>{ext}</lyric>'
                         f'<lyric number="2"><syllabic>single</syllabic><text>{tone_mark(py)}</text></lyric>')
            pitch = f"<pitch><step>{STEPS[m % 12]}</step>" + (f"<alter>{ALTERS[m % 12]}</alter>" if ALTERS[m % 12] else "") + \
                    f"<octave>{m // 12 - 1}</octave></pitch>"
            x.append(f"<note>{pitch}<duration>{d}</duration><type>{typ}</type>{dot}{notations}{lyric}</note>")
        if b == max(by_bar):
            x.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
        x.append("</measure>")
    x += ["</part>", "</score-partwise>"]
    Path(path).write_text("\n".join(x), encoding="utf-8")


def write_midi(path, song, evs, bpm, lyric_mode, hold="-", lead=None):
    """單軌 SMF type 0；每個音前放一個 lyric meta（0x05）：漢字或拼音（不帶調），一字多音的後續音放延續記號。
    lead：第一個音前空幾個十六分音符，預設讓弱起落在第 1 小節的對應拍"""
    if lead is None:
        lead = BAR - song.pickup_len if song.pickup_len else 0
    tpq = 480
    tick = tpq // 4
    trk = bytearray(tempo_meta(bpm))
    name = song.title.encode("utf-8")
    trk += vlq(0) + b"\xff\x03" + vlq(len(name)) + name
    now = 0
    for t, d, m, char, py, first, _ in evs:
        if m is None:
            continue
        on, off = (t + lead) * tick, (t + lead + d) * tick
        text = (char if lyric_mode == "hanzi" else py[:-1]) if first else hold
        lb = text.encode("utf-8")
        trk += vlq(on - now) + b"\xff\x05" + vlq(len(lb)) + lb
        trk += vlq(0) + bytes([0x90, m, 96])
        trk += vlq(off - on) + bytes([0x80, m, 0])
        now = off
    trk += vlq(0) + b"\xff\x2f\x00"
    Path(path).write_bytes(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq) + b"MTrk" + struct.pack(">I", len(trk)) + trk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--key", help="輸出的調，省略＝譜面原調")
    ap.add_argument("--bpm", type=float, default=110)
    ap.add_argument("--intro-bars", type=int, default=0, help="人聲 MIDI 前面再空幾小節（給 arrange.py 的前奏）")
    ap.add_argument("--out")
    a = ap.parse_args()
    song = Song(a.song, a.key)
    evs = song.events()
    out = Path(a.out) if a.out else song.path.parent
    stem = f"{song.stem}_{song.key}調_{a.bpm:g}BPM" + (f"_前奏{a.intro_bars}小節" if a.intro_bars else "")
    if a.intro_bars:
        lead = BAR * (a.intro_bars + 1) - song.pickup_len
        write_midi(out / f"{stem}_OpenUtau.mid", song, evs, a.bpm, "pinyin", hold="+", lead=lead)
        print(f"{stem}_OpenUtau.mid：第一個字在 {lead * 15 / a.bpm:.2f} 秒")
        return
    write_musicxml(out / f"{stem}.musicxml", song, evs, a.bpm)
    write_midi(out / f"{stem}_漢字.mid", song, evs, a.bpm, "hanzi")
    write_midi(out / f"{stem}_拼音.mid", song, evs, a.bpm, "pinyin")
    write_midi(out / f"{stem}_OpenUtau.mid", song, evs, a.bpm, "pinyin", hold="+")
    y = melody_wave(evs, a.bpm)
    write_wav(out / f"{stem}_試聽.wav", y / np.abs(y).max() * 0.8)
    chars = sum(1 for e in evs if e[5] and e[2] is not None)
    notes = sum(1 for e in evs if e[2] is not None)
    print(f"{stem}：{chars} 字、{notes} 個音、{song.length16() * 15 / a.bpm:.1f} 秒")


if __name__ == "__main__":
    main()
