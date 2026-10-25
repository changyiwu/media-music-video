# media-music-video（專案藍圖）

> 本檔為跨 Agent 通用的專案藍圖（AGENTS.md 開放標準）。任何 Agent 的每個 session 都應先讀本檔＋`handoff.md`。
> Claude Code 預設只在沒有 `CLAUDE.md` 時才讀 `AGENTS.md`，故由 `CLAUDE.md` 的 `@AGENTS.md` import 本檔（`CLAUDE.md` 只有這一行）；Claude 專屬規範寫在本檔〈Claude Code 專屬〉一節。

## 專案簡介

做**歌曲與配樂影片**：用本機 ComfyUI（Music 3）作曲、生圖，再用程式動畫做歌詞 MV、動態設計等配樂影片。
H3 劇情短片改在 `media-short-film` 專案做，純 Blender 作品改在 `media-3d-studio` 做（2026-10-25 起，已把相關作品搬過去）。
本專案只放**創作本身**——每件作品的筆記、生成腳本、工作流程 JSON。ComfyUI 怎麼操作、各模型的欄位與提示詞規則，
以已安裝的 `comfyui` 技能為準（原始檔在 `agent-setup-guide` repo 的 `skills/07-comfyui/`）；
在這裡實測出的**通用**經驗寫回那個技能，這件作品專屬的東西才留在這裡。

## 關鍵時程

- 2026-09-15：歌曲〈衝破這片天〉（Music 3 三版＋Z-Image 封面，做成 FB 影片），09-18 整理進 `output/power-ballad/`
- 2026-09-16～18：第一支片「古裝庭院惡搞短片」完成（四段、23 秒；2026-10-25 移至 `media-short-film/films/原創短劇/臭豆腐/`）
- 2026-09-18：專案初始化（原名 `ai-video-studio`），從 `agents-lazy-guide/comfyui/` 整批搬入工作流程與實驗檔；
  同日收進歌曲作品、範圍擴大到影音作品，改名 `ai-media-studio`（GitHub 舊網址自動轉址）；2026-10-20 全 agents/ 改名為 `media-comfyui-studio`
- 2026-09-28：〈衝破這片天〉歌曲定稿為剪接版（134 秒），並做成動態歌詞 MV（各行各業版，`output/power-ballad/lyric-video/`；
  畫面全用程式畫，歌曲仍是 Music 3）
- 2026-09-29：仿蘋果發表廣告〈Banana 18 Pro〉60 秒 v3 完成（2026-10-25 移至 `media-3d-studio/output/banana-18-pro/`）——第一件**不用 ComfyUI**、
  全程式製作的作品（Blender bpy 建模算圖＋Python 合成＋numpy 合成配樂）
- 2026-10-09：15 秒動態設計 showreel〈動態設計作品集〉（`output/motion-showreel/`）——Canvas 2D 全程式動畫＋numpy 配樂，128 BPM 八場對拍；同日另做 HyperFrames 比較版（`hf/`）
- 2026-10-11：測試 Blender 灰模動作片當 H3 Ref2VA 參考影片（2026-10-25 瘦身後移至 `media-short-film/films/測試/測試_H3灰模動作參考/`）——動作會照做、時間逐格對齊，
  推翻先前「Blender previz 這條路劃掉」的結論（只對機位成立）；結論寫回 `comfyui`（guide v0.15）
- 2026-10-12：同一測試補三項——人物照＋灰模動作片可同時用（指定的人做指定的動作）、灰模片的運鏡會跟且壓過文字、
  動作句不提 `<Video 1>` 時參考片幾乎無效但照樣慢 3.5 倍（guide v0.16）
- 2026-10-13：路線圖階段三完成（`tools/ref2va.py`，2026-10-25 由 media-short-film 的 `h3_shot.py` 取代、封存進《臭豆腐》）；動作參考第三輪——手指逐根照做、10 秒照做，
  人偶臉的色塊五官會被貼到真人臉上（改同色浮雕即可），同一句裡衝突會兩邊各做一半（guide v0.17）
- 2026-10-13：動作參考第四輪（電腦 B）——同色浮雕臉換 seed 仍被貼上五官，改成同材質挖凹陷才兩個 seed 都乾淨且表情對時；
  雙人各做各的動作放同一支參考片即可（分兩支接成本翻倍）；參考片的音軌接了就被原樣搬進成品、提示詞不提也一樣（guide v0.18）
- 2026-10-25：H3 短片與測試搬到 `media-short-film`、〈Banana 18 Pro〉搬到 `media-3d-studio`，刪除 `tools/ref2va.py`
- 2026-10-25：依留下的作品（兩首歌＋MV、一支配樂 showreel）改名 `media-comfyui-studio` → `media-music-video`（資料夾、GitHub repo、Obsidian 同步改）；
  同日 `experiments/` 與 H3 範本移到 `media-short-film/films/測試/早期實驗/`，SOP 的 H3 影片段落改指向該專案 `docs/`

## 目標與路線圖

- [x] 階段一：第一支短片完成並定稿（《臭豆腐》，現在 `media-short-film`）
- [x] 階段二：通用經驗寫回 `comfyui` 技能（agent-setup-guide guide v0.14）
- [x] 階段三：把《臭豆腐》的 `build_seg.py` 抽成不綁定單一支片的分段產生器（`tools/ref2va.py`；已由 media-short-film 的 `tools/h3_shot.py` 取代並刪除）

## 資料夾結構

```
media-music-video/
├── AGENTS.md            本檔（專案藍圖）
├── handoff.md           交接檔（不進 git）
├── CLAUDE.md            橋接檔（@AGENTS.md）
├── docs/                作品製作 SOP、發布檢查清單、動畫 MV 畫面規則（模型知識指向 comfyui 技能，不另存一份）
├── output/              所有產出（不進 git，只走雲端硬碟同步）；一件作品一個資料夾（影片、音樂、圖片都一樣）
│   ├── <slug>/media/    該作品生成的影音與圖片（audio/、image/、video/）
│   ├── power-ballad/    華語搖滾抒情歌〈衝破這片天〉（2026-09，Music 3＋封面）與全程式動態歌詞 MV
│   │   ├── notes.md     三版演進、剪接定稿版、MV 各版紀錄、成品清單
│   │   ├── lyric-video/ 動態歌詞 MV 原始專案（Canvas 2D 骨架動畫＋KTV 字幕，各行各業版）
│   │   └── workflows/   從 mp3／PNG metadata 取回的工作流程
│   ├── teachers-day-kpop/ 教師節歌曲〈把光留給我〉與生圖＋程式動畫 MV
│   │   ├── notes.md     歌曲、試片、全曲 v1／v2 的作品紀錄
│   │   ├── mv/          10 秒試片來源
│   │   ├── mv-full/     全曲 v1 來源
│   │   └── mv-full-v2/  全曲 v2 來源、分鏡與驗收紀錄
│   └── motion-showreel/ 15 秒動態設計 showreel（Canvas 2D 逐格＋Headless Edge 擷取＋numpy 配樂）
│       └── hf/          同一支片的 HyperFrames 比較版（登錄元件＋GSAP＋Three.js，配樂共用）
├── templates/           官方工作流程快照（Z-Image、Qwen Image Edit）、發布資訊範本.md（YouTube／Facebook／Instagram／Threads；五個媒體專案各一份、內容逐位元組相同，正本在 media-youtube-publish 的 `skills/youtube-video-workflow/references/`，改正本再整份覆蓋，不在本專案就地改）
└── scratch/             comfy-cli 回傳、節點資訊、紀錄等暫存（不進 git）
```

生成的影片、音樂、圖片（含抽幀驗收圖、字幕）產出後**從 ComfyUI 的 output 資料夾搬到該作品的 `output/<slug>/media/`**，
保留 `audio/`、`image/`、`video/` 子結構。定稿檔的路徑記在各片的 `notes.md`。

## 專案專屬規則

- **ComfyUI 的操作方式與模型規則不在本專案另存一份**，一律照 `comfyui` 技能與它的 `models/` 筆記。
  實測出通用經驗就寫回 agent-setup-guide 的技能與 guide，本專案只留該片專屬的設定與決定。
- **製作流程與發布把關照 `docs/production-sop.md`**：開新作品的順序、跨作品已定案的選型、三種格式的 metadata
  清除與雙重驗證指令都在那裡。跨作品的決策定案後寫進該檔第五節，**不要在各作品的 `notes.md` 各留一份**。
  用 ComfyUI（H3）做劇情／多段影片不在本專案做，流程與定案以 `media-short-film` 的 `docs/` 為準。
- **做動畫或歌詞 MV（程式畫或生圖合成都算）前，先讀該檔第五節〈動畫／歌詞 MV 的畫面規則〉**：
  字幕位置與 KTV 掃色、坐姿要有椅子、手要碰到東西、朝向、不做危險動作等都是使用者定案的驗收條件。
- **使用者的照片、聲音、完整提示詞只放在本私有專案**，不得寫進 agent-setup-guide（公開 repo）；
  寫回技能時情境一律用通稱（例如「古裝庭院雙人短片」）。
- **社群發布文案照 [templates/發布資訊範本.md](templates/發布資訊範本.md)**：作品驗收通過後複製成 `output/<slug>/發布資訊.md`，依實際流程填寫 AI 揭露、工具名單與平台文案，發布後記錄公開網址。
- **對外發布的成品一律另存一份清掉 metadata 的版本**，並用 `ffprobe`（圖片看 PNG 的 `prompt` 區塊）與位元組掃描驗證
  不含 `prompt`；ComfyUI 的原始輸出檔不動。影片、**mp3**（內嵌歌詞全文）、PNG 都會帶工作流程。
- **聲音由使用者試聽**（agent 聽不到），包括台詞、參考聲音像不像、段落接點的環境音。
- 每件作品一個資料夾 `output/<slug>/`，至少有 `notes.md`；`scratch/` 放暫存、不進 git。
- 換電腦重現作品前，先等該作品的 `output/<slug>/` 雲端同步完成，再調整 `local-config.json`；本機設定檔維持忽略，不提交 Git。
- 程式算圖的中間檔（上千張分鏡 PNG、配樂 wav）**放本機暫存資料夾，不要放進雲端硬碟**；專案只留腳本，成品放該作品的 `output/<slug>/media/`。
- **音訊與訊號處理只用 numpy**（濾波用 FFT／STFT 自寫），不要讓作品腳本依賴 scipy：Windows 的智慧型應用程式控制會擋 scipy 的 DLL。
  電腦 A 已於 2026-10-11 關閉它（ComfyUI 0.39.2 起一啟動就載入 scipy，開著 ComfyUI 整個起不來）；其他電腦開著的話會遇到同樣問題。
- 舊作品的工作流程若沒留檔，**從輸出檔內嵌的 metadata 取回**（mp3／mp4 的 `format_tags.prompt`、PNG 的 `prompt` 區塊），不要憑記憶重寫。

## 同步層級（本專案初始化至第三層級）

| 層級 | 平台 | 位置 | 讀取時機 |
|------|------|------|---------|
| L1 | 本地（GDrive） | `AGENTS.md`＋`handoff.md`（不進 git，只走雲端硬碟）＋`CLAUDE.md`（橋接） | 每個 session |
| L2 | GitHub | [changyiwu/media-music-video](https://github.com/changyiwu/media-music-video)（**私有**） | 指定時 |
| L3 | Obsidian | `media-music-video/專案工作流程.md` | 有需要時 |

## 三個檔案的職責（依「時效性」分家，不是依「詳細程度」）

| 檔案 | 時效 | 寫入方式 | 放什麼 |
|------|------|---------|--------|
| `handoff.md` | **只對下一個 session 有效**，過期即丟 | 每次收工**整份重寫** | 做到哪、下一步、**這次**的暫時 workaround |
| `AGENTS.md`（本檔） | **長期有效**，每個 session 都適用 | 只有規則本身變了才改 | 目標、路線圖、常設規則、結構 |
| Obsidian（L3）／`git log` | **歷史**：發生過什麼、為什麼 | 只增不刪 | 決策紀錄、踩坑完整版、逐次進度 |

驗收標準：**`handoff.md` 整份刪掉，不應損失任何長期資訊**——會的話代表該升級進本檔卻沒升級。

**本檔不要出現的東西**（會無限膨脹，且開工每次都要重讀）：
- ❌ `## 最近進度`／逐次工作紀錄 → 寫 Obsidian「🗓️ 最近更動紀錄」
- ❌ 決策記錄、取捨理由、踩坑經過的完整版 → Obsidian「決策紀錄」「🕳️ 踩坑筆記」
- ✅ 只留「結論式的規則」：踩過的坑收斂成一條**祈使句**寫進〈工作約定〉或〈專案專屬規則〉，理由那一大段留在 Obsidian

## 工作約定
- 任何 Agent、任何電腦：**開工先讀 `handoff.md`，收工必更新 `handoff.md`**
- `handoff.md` **不進 git**（含真實電腦名與本機絕對路徑），已列入 `.gitignore`，跨電腦靠雲端硬碟同步——不要把它加回版控
- 修改共用檔案前先讀最新內容，避免覆蓋其他 Agent 的變更
- 所有回應與文件使用繁體中文
- 修改前先確認計畫，優先保留原有資料結構
- **產出一律放 `output/`**：本專案產生的檔案或資料夾（成品、匯出、報表、生成圖、渲染等）預設放專案根目錄的 `output/`，不另開 `outputs/`、`exports/`、`generated/`、`out/` 之類的資料夾，方便找；`output/` 不進 git。部署工具指定的建置目錄（`dist/`、`build/`）不在此限。本專案每件作品一個 `output/<slug>/`，生成的影音放其中的 `media/`
