# media-music-video

歌曲與配樂影片的作品庫：用本機 ComfyUI（Music 3）作曲、生圖，再用程式動畫做歌詞 MV、動態設計等配樂影片；照譜唱的歌改走 OpenUtau 歌聲合成＋程式編曲。

本 repo 只管**規則、工具與範本**；作品本身（音樂、影片、圖片、工作檔）都在 `output/`，不進 git，只走雲端硬碟同步。劇情短片在 `media-short-film`、純 Blender 作品在 `media-3d-studio`，不在這裡做。

## 開始之前

- 先讀 [AGENTS.md](AGENTS.md)（專案藍圖：資料夾結構、作品命名、發布把關），再讀 `handoff.md`（上次做到哪，不進 git）。
- 開新作品、選型與發布前的 metadata 清除照 [docs/production-sop.md](docs/production-sop.md)；做動畫或歌詞 MV 前先讀它第五節的畫面規則。
- 使用者給了譜、要照譜照詞唱的歌，照 [docs/照譜唱歌曲流程.md](docs/照譜唱歌曲流程.md)，不用 ComfyUI。
- ComfyUI 的操作與模型規則以已安裝的 `comfyui` 技能為準，本專案不另存一份。

## 目錄

```text
media-music-video/
├── AGENTS.md        專案藍圖（規則都在這裡）
├── CLAUDE.md        Claude Code 橋接檔（@AGENTS.md）
├── docs/            製作 SOP、照譜唱歌曲流程
├── tools/sing/      照譜唱工具：song.json → 人聲 MIDI、和弦、編曲、FluidSynth 算圖、混音（numpy＋ffmpeg）
├── tools/mv/        歌詞 MV 節拍分析（listen.py）
├── styles/          畫風庫（見 styles/README.md）
├── templates/       官方工作流程快照（Z-Image、Qwen Image Edit）、發布資訊範本.md
└── output/          作品，`output/<類型>/<作品名>/`（類型：歌曲MV、動態設計；不進 git）
```

## 需要的環境

- 本機 ComfyUI（`comfy-cli`）與 `comfyui` 技能
- Python＋numpy、ffmpeg；照譜唱另需 OpenUtau 與 FluidSynth
- 作品腳本不依賴 scipy（Windows 智慧型應用程式控制會擋它的 DLL），`tools/mv/listen.py` 例外，在獨立虛擬環境跑

## 第三方內容

`styles/lemo-opuscar/`、`styles/huashu-art-motion/` 與 `tools/mv/listen.py`（取自 mv-director）是 MIT 授權的上游內容，授權檔放在各自資料夾，只借用畫法與節拍分析。

## 授權

- 本專案自寫的程式與文件採 [MIT](LICENSE)。
- [templates/發布資訊範本.md](templates/發布資訊範本.md) 例外：改作自山獅霸的多重宇宙的範本，採 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hant)（不可商用），出處寫在該檔末尾。
- 上面「第三方內容」列的資料夾依各自的 LICENSE（MIT，著作權屬原作者）。
- `templates/qedit.json`、`templates/zimg.json` 是 ComfyUI 官方範本的工作流程快照，依 ComfyUI 範本原本的授權。
