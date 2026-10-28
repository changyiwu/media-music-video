"""用 FluidSynth＋SoundFont 把伴奏 MIDI 算成真樂器 wav，剪掉尾端殘響並淡出。

用法：python render.py <伴奏.mid> <輸出.wav> [--sf GeneralUser-GS] [--gain 0.6] [--tail 3.4] [--fade 1.5] [--hall]
- --sf：音色庫檔名（不含 .sf2，在 media-tools 的 soundfont 資料夾裡找）或完整路徑；樂團用 GeneralUser-GS，管弦樂用 MuseScore_General
- --hall：開大廳殘響（管弦樂用；FluidSynth 內建殘響、房間 0.75、濕度 0.35）
- 長度＝MIDI 最後一個事件＋tail 秒，最後 fade 秒淡出（FluidSynth 會把殘響算到很長）
- 工具位置依序找：環境變數 FLUIDSYNTH／SOUNDFONT → 專案根目錄 local-config.json 的 "fluidsynth"／"soundfont"
  → %LOCALAPPDATA%\\media-tools\\ 底下（安裝方式見 docs/照譜唱歌曲流程.md）
- 需要 ffmpeg（剪長度、淡出）
"""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_tool(env, key, pattern):
    if os.environ.get(env):
        return Path(os.environ[env])
    cfg = ROOT / "local-config.json"
    if cfg.exists():
        v = json.loads(cfg.read_text(encoding="utf-8")).get(key)
        if v:
            return Path(v)
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "media-tools"
    hits = sorted(base.glob(pattern))
    if not hits:
        raise SystemExit(f"找不到 {key}：設環境變數 {env}、local-config.json 的 \"{key}\"，或放到 {base}")
    return hits[-1]


def midi_seconds(path):
    """讀 SMF，回傳最後一個事件的秒數（支援 running status 與中途換速度）"""
    data = Path(path).read_bytes()
    ntrk, tpq = int.from_bytes(data[10:12], "big"), int.from_bytes(data[12:14], "big")
    pos, tempos, last = 14, [], 0

    def vlq(p):
        n = 0
        while True:
            b = data[p]
            p += 1
            n = (n << 7) | (b & 0x7F)
            if b < 0x80:
                return n, p

    for _ in range(ntrk):
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        p, end, tick, status = pos + 8, pos + 8 + size, 0, 0
        while p < end:
            dt, p = vlq(p)
            tick += dt
            if data[p] & 0x80:
                status = data[p]
                p += 1
            if status == 0xFF:
                typ = data[p]
                ln, p = vlq(p + 1)
                if typ == 0x51:
                    tempos.append((tick, int.from_bytes(data[p:p + 3], "big")))
                p += ln
            elif status in (0xF0, 0xF7):
                ln, p = vlq(p)
                p += ln
            else:
                p += 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            last = max(last, tick)
        pos = end
    tempos = sorted(tempos) or [(0, 500000)]
    sec, prev_tick, us = 0.0, 0, 500000
    for t, u in tempos:
        if t >= last:
            break
        sec += (t - prev_tick) * us / tpq / 1e6
        prev_tick, us = t, u
    return sec + (last - prev_tick) * us / tpq / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("midi")
    ap.add_argument("out")
    ap.add_argument("--sf", default="GeneralUser-GS")
    ap.add_argument("--hall", action="store_true")
    ap.add_argument("--gain", type=float, default=0.6)
    ap.add_argument("--tail", type=float, default=3.4)
    ap.add_argument("--fade", type=float, default=1.5)
    a = ap.parse_args()
    fs = find_tool("FLUIDSYNTH", "fluidsynth", "fluidsynth*/**/bin/fluidsynth.exe")
    sf = Path(a.sf) if Path(a.sf).suffix else find_tool("SOUNDFONT", "soundfont", f"soundfont/{a.sf}.sf2")
    length = midi_seconds(a.midi) + a.tail
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw.wav"
        hall = ["-R", "1", "-o", "synth.reverb.room-size=0.75", "-o", "synth.reverb.damp=0.35",
                "-o", "synth.reverb.width=1.0", "-o", "synth.reverb.level=0.6"] if a.hall else []
        subprocess.run([str(fs), "-ni", "-q", "-g", str(a.gain), "-r", "44100", *hall, "-F", str(raw), str(sf), a.midi], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-t", f"{length:.3f}",
                        "-af", f"afade=t=out:st={length - a.fade:.3f}:d={a.fade}", "-c:a", "pcm_s16le", a.out], check=True)
    print(f"{a.out}：{length:.1f} 秒（{sf.name}）")


if __name__ == "__main__":
    main()
