"""照 song.json 算逐字時間，寫成 src/lyrics-data.js（必要時另出 SRT）。

照譜唱的歌，每個字幾時唱、唱多長都寫在譜上，不必再用 Whisper 對時間：
字的起點＝伴奏前奏＋過門小節之後的位置（與 arrange.py 的 vocal_at 相同），長度＝這個字所有音的長度和。
休止 ≥ --gap 個十六分音符就斷句。

用法：python build_lyrics.py <song.json> --bpm 100 --intro-bars 4 [--gap 4] [--srt 輸出.srt]
（--bpm、--intro-bars 要跟 arrange.py、score.py 用的一樣，字幕才會對到音樂）
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools" / "sing"))
from song import BAR, Song  # noqa: E402

LEAD_IN = 0.6   # 字幕比第一個字早幾秒出現
HOLD = 0.5      # 最後一個字唱完後多留幾秒（不超過下一句開始）


def build(song, bpm, intro, gap):
    sec16 = 60 / bpm / 4
    vocal_at = BAR * (intro + 1) - song.pickup_len
    lines, cur, rest = [], [], 0
    for t, d, m, ch, py, first, _ in song.events():
        if m is None:
            rest += d
            if rest >= gap and cur:
                lines.append(cur)
                cur = []
            continue
        rest = 0
        if first:
            cur.append({"c": ch, "t": round((vocal_at + t) * sec16, 3), "e": round((vocal_at + t + d) * sec16, 3)})
        else:
            cur[-1]["e"] = round((vocal_at + t + d) * sec16, 3)  # 一字多音：延長同一個字
    if cur:
        lines.append(cur)
    out = []
    for i, chars in enumerate(lines):
        start = max(0, chars[0]["t"] - LEAD_IN)
        out.append({"id": i + 1, "text": "".join(c["c"] for c in chars), "start": round(start, 3), "chars": chars})
    for i, L in enumerate(out):
        nxt = out[i + 1]["start"] if i + 1 < len(out) else 1e9
        L["end"] = round(min(L["chars"][-1]["e"] + HOLD, nxt), 3)
    return out


def srt_time(s):
    ms = round(s * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--intro-bars", type=int, default=4)
    ap.add_argument("--gap", type=int, default=4, help="休止多長（十六分音符）就斷句")
    ap.add_argument("--srt")
    a = ap.parse_args()
    lines = build(Song(a.song), a.bpm, a.intro_bars, a.gap)
    js = HERE.parent / "src" / "lyrics-data.js"
    js.write_text("// tools/build_lyrics.py 產生，不要手改。每字 t＝開始唱、e＝唱完（秒）。\nwindow.LYRICS = "
                  + json.dumps(lines, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"寫好 {js}：{len(lines)} 句")
    for L in lines:
        print(f"  {L['start']:6.2f}–{L['end']:6.2f}  {L['text']}")
    if a.srt:
        rows = [f"{L['id']}\n{srt_time(L['start'])} --> {srt_time(L['end'])}\n{L['text']}\n" for L in lines]
        Path(a.srt).write_text("\n".join(rows), encoding="utf-8")
        print(f"寫好 {a.srt}")


if __name__ == "__main__":
    main()
