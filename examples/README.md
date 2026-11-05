# 範例：從一份歌譜做出一支歌詞 MV

本專案的作品（歌曲、MV 原始專案）都放在不進 git 的 `output/`，所以另外做了這個**可以完整跑一遍的最小範例**。
歌〈走到天亮〉是本 repo 自寫的 8 小節示範曲（詞曲都是範例用，跟任何作品無關），畫面全用程式畫，不用生成模型、照片或外部圖片。

```text
examples/song/song.json ──tools/sing/arrange.py──▶ 伴奏＋旋律導引 wav（numpy 合成，當作試聽用的歌）
        │
        └──examples/lyric-mv/tools/build_lyrics.py──▶ 逐字時間 src/lyrics-data.js（照譜算，不用對嘴）
                                                         │
                         examples/lyric-mv/index.html ◀──┘  Canvas 2D 逐格畫面（時間 t 的純函數）
                                 │
                         tools/render.mjs（無頭 Edge／Chrome 逐格擷取 → ffmpeg）──▶ MP4
```

成品約 35 秒、1920×1080、30 fps：黎明原野 → 窗邊晨光爬上窗台 → 窗簾被風吹起、人伸懶腰 → 大人牽小孩往前走 → 太陽升起、兩人舉手 → 片名。

## 需要的環境

- Python 3＋numpy
- Node.js 18 以上（只用內建模組，不必 `npm install`）
- Microsoft Edge 或 Google Chrome（找不到時用 `--browser <路徑>` 指定）
- ffmpeg（要在 PATH 裡）
- 字型：Noto Sans TC（沒有的話會改用微軟正黑體或 PingFang TC）

## 跑一遍（在 repo 根目錄）

1. 從歌譜做出音樂。輸出放暫存資料夾，不要放進 repo：

```bash
python -X utf8 tools/sing/arrange.py examples/song/song.json --bpm 100 --intro-bars 4 --out <暫存資料夾>
```

它會印出「人聲第一個字在 12.00 秒」。這次要用的是 `伴奏預覽_輕快版_100BPM_含旋律導引.wav`，把它複製成 `examples/lyric-mv/audio.wav`（`.wav` 不進 git）。

2. 照譜算逐字時間。`--bpm`、`--intro-bars` 要跟上一步一樣：

```bash
python -X utf8 examples/lyric-mv/tools/build_lyrics.py examples/song/song.json --bpm 100 --intro-bars 4
```

repo 裡已經有一份算好的 `src/lyrics-data.js`；改了歌譜才需要重跑。

3. 預覽：在 `examples/lyric-mv/` 起一個靜態伺服器，用瀏覽器開，就能跟著音樂播放、拖時間軸。

```bash
cd examples/lyric-mv && python -m http.server 8000
```

開 `http://127.0.0.1:8000/`，網址加 `?t=21` 可以從第 21 秒開始。

4. 檢查與出片（都在 `examples/lyric-mv/` 底下跑）：

```bash
node tools/render.mjs --check 0.25
```

```bash
node tools/render.mjs --stills 2,14,19.5,23,29.8,33 --outdir <暫存資料夾>
```

```bash
node tools/render.mjs --workers 4 --audio audio.wav --out <暫存資料夾>/走到天亮_範例.mp4
```

`--check` 每 0.25 秒畫一格，列出「手構不到該碰的東西」「手臂往身後反折」，要印出「全部構得到、沒有反折」才出片；`--stills` 抽幾格 PNG 目視。
4 個平行程序算完整支約 10–20 秒；32 GB RAM 最多開 6 個。

## 要換成自己的歌

- **自己的譜**：照 [tools/sing/song.py](../tools/sing/song.py) 檔頭的格式寫 `song.json`，流程見 [docs/照譜唱歌曲流程.md](../docs/照譜唱歌曲流程.md)。
  真人聲要用 OpenUtau 照 `score.py` 輸出的 MIDI 唱，伴奏用 `render.py`（FluidSynth）算真樂器，再用 `mix.py` 混音；
  這裡的旋律導引只是合成音，用來對時間。
- **不是照譜的歌**（例如 AI 作曲）：沒有譜可算逐字時間，改用 Whisper 取逐字時間＋起音分析，節拍用 [tools/mv/listen.py](../tools/mv/listen.py)；做法見 [docs/production-sop.md](../docs/production-sop.md) 第五節。
- **畫面**：分鏡表在 `src/timeline.js` 的 `SHOTS`，時間一律寫「第幾小節」；改 BPM 時同步改 `TL.BPM`、`TL.DUR`（`arrange.py` 印出來的秒數）。
  畫面規則（字幕位置、KTV 掃色、手要碰到東西、手不反折、多人不鏡像……）見 production-sop 第五節〈動畫／歌詞 MV 的畫面規則〉，這個範例都照做了。
- 畫風可以從 `media-code-video` 的[畫風庫](https://github.com/changyiwu/media-code-video/blob/main/styles/README.md)挑。

## 檔案

```text
examples/
├── song/song.json              示範歌譜（C 調、4/4、8 小節；拼音逐字標聲調）
└── lyric-mv/
    ├── index.html              預覽播放器＋渲染入口（window.renderAt(t)）
    ├── src/timeline.js         ★ 速度、分鏡表（字面／畫面／關鍵詞）、字幕樣式
    ├── src/scenes.js           原野、窗邊兩個場景＋片名、閃光、淡出
    ├── src/rig.js              2D 人物骨架（FK＋兩段式 IK、實心剪影、構不到與反折的檢查）
    ├── src/subs.js             KTV 字幕（下方、小字、唱到哪掃到哪）
    ├── src/engine.js           緩動、關鍵影格、可重現亂數、積分表
    ├── src/lyrics-data.js      ← build_lyrics.py 產生，不要手改
    └── tools/                  build_lyrics.py、render.mjs
```
