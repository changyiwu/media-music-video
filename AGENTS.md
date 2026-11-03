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

- 2026-09-15：歌曲〈衝破這片天〉（Music 3 三版＋Z-Image 封面，做成 FB 影片），09-18 整理進 `output/power-ballad/`（現為 `output/歌曲MV/衝破這片天/`）
- 2026-09-16～18：第一支片「古裝庭院惡搞短片」完成（四段、23 秒；2026-10-25 移至 `media-short-film/output/原創短劇/臭豆腐/`）
- 2026-09-18：專案初始化（原名 `ai-video-studio`），從 `agents-lazy-guide/comfyui/` 整批搬入工作流程與實驗檔；
  同日收進歌曲作品、範圍擴大到影音作品，改名 `ai-media-studio`（GitHub 舊網址自動轉址）；2026-10-20 全 agents/ 改名為 `media-comfyui-studio`
- 2026-09-28：〈衝破這片天〉歌曲定稿為剪接版（134 秒），並做成動態歌詞 MV（各行各業版，現在 `output/歌曲MV/衝破這片天/MV-各行各業/`；
  畫面全用程式畫，歌曲仍是 Music 3）
- 2026-09-29：仿蘋果發表廣告〈Banana 18 Pro〉60 秒 v3 完成（2026-10-25 移至 `media-3d-studio/output/banana-18-pro/`）——第一件**不用 ComfyUI**、
  全程式製作的作品（Blender bpy 建模算圖＋Python 合成＋numpy 合成配樂）
- 2026-10-09：15 秒動態設計 showreel〈動態設計作品集〉（`output/動態設計/動態設計作品集/`）——Canvas 2D 全程式動畫＋numpy 配樂，128 BPM 八場對拍；同日另做 HyperFrames 比較版（`hf/`）
- 2026-10-11：測試 Blender 灰模動作片當 H3 Ref2VA 參考影片（2026-10-25 瘦身後移至 `media-short-film/output/測試/測試_H3灰模動作參考/`）——動作會照做、時間逐格對齊，
  推翻先前「Blender previz 這條路劃掉」的結論（只對機位成立）；結論寫回 `comfyui`（guide v0.15）
- 2026-10-12：同一測試補三項——人物照＋灰模動作片可同時用（指定的人做指定的動作）、灰模片的運鏡會跟且壓過文字、
  動作句不提 `<Video 1>` 時參考片幾乎無效但照樣慢 3.5 倍（guide v0.16）
- 2026-10-13：路線圖階段三完成（`tools/ref2va.py`，2026-10-25 由 media-short-film 的 `h3_shot.py` 取代、封存進《臭豆腐》）；動作參考第三輪——手指逐根照做、10 秒照做，
  人偶臉的色塊五官會被貼到真人臉上（改同色浮雕即可），同一句裡衝突會兩邊各做一半（guide v0.17）
- 2026-10-13：動作參考第四輪（電腦 B）——同色浮雕臉換 seed 仍被貼上五官，改成同材質挖凹陷才兩個 seed 都乾淨且表情對時；
  雙人各做各的動作放同一支參考片即可（分兩支接成本翻倍）；參考片的音軌接了就被原樣搬進成品、提示詞不提也一樣（guide v0.18）
- 2026-10-25：H3 短片與測試搬到 `media-short-film`、〈Banana 18 Pro〉搬到 `media-3d-studio`，刪除 `tools/ref2va.py`
- 2026-10-25：依留下的作品（兩首歌＋MV、一支配樂 showreel）改名 `media-comfyui-studio` → `media-music-video`（資料夾、GitHub repo、Obsidian 同步改）；
  同日 `experiments/` 與 H3 範本移到 `media-short-film/output/測試/早期實驗/`，SOP 的 H3 影片段落改指向該專案 `docs/`
- 2026-10-26：作品資料夾比照 `media-short-film` 改成 `output/<類型>/<作品名>/`（歌曲MV／動態設計）：定案成品放最上層、工作檔放 `work/`、舊版放 `舊版/`，`notes.md` 改名 `製作紀錄.md`
- 2026-10-28：〈校歌〉輕快改編——YuE2 確定把中文唱成粵語，YuE2／ACE-Step 能否逐音照譜 10-29 改為未確定（經驗寫回 comfyui 技能），改走 OpenUtau 歌聲合成＋程式編曲＋FluidSynth；
  同日把這首的腳本整理成共用的 `tools/sing/` 與 `docs/照譜唱歌曲流程.md`
- 2026-11-01：評估 `Yari-tuber/mv-director`：只移植節拍分析（`tools/mv/listen.py`）與逐句分鏡方法；強制對齊試聽後不用，成片審查門檻不適合抒情 MV 也不移植；
  同日搬入兩個畫風庫的文字規則到 `styles/`，不搬樣片、工具與上游的 agent 指令檔
- 2026-11-03：〈衝破這片天〉有四版 MV（各行各業、流場筆觸、水墨一筆、沙畫），各放一個 `MV-<畫風>/` 子資料夾、製作紀錄各一份；定案的各行各業版改名 `衝破這片天_各行各業.mp4`

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
├── docs/                作品製作 SOP、發布檢查清單、動畫 MV 畫面規則（模型知識指向 comfyui 技能，不另存一份）、照譜唱歌曲流程
├── tools/sing/          照譜唱歌曲工具（song.json → 人聲 MIDI、和弦、輕快編曲、FluidSynth 算圖、混音；只用 numpy＋ffmpeg）
├── tools/mv/            歌詞 MV 節拍分析（listen.py，取自 mv-director，MIT；只採用拍點與小節）
├── styles/              畫風庫（lemo-opuscar、huashu-art-motion 的畫風文字與少量畫法程式，MIT；只借畫法，見 styles/README.md）
├── output/              所有產出（不進 git，只走雲端硬碟同步）；一件作品一個資料夾 `output/<類型>/<作品名>/`
│   ├── <類型>/<作品名>/  最上層放定案成品與文件：<作品名>.mp4、_社群版.mp4、_手機版.mp4、<作品名>.mp3、字幕 .srt、
│   │                    cover*.png、製作紀錄.md、發布資訊.md、歌詞.txt、主腳本；工作檔放 work/，舊版放 舊版/
│   ├── 歌曲MV/
│   │   ├── 衝破這片天/   華語搖滾抒情歌（2026-09，Music 3＋封面）與四版全程式 MV；最上層放歌曲成品、封面、發布資訊
│   │   │   ├── work/     歌曲共用：audio/、video/、image/、workflows/（從 metadata 取回）、analysis/（listen.py 節拍）
│   │   │   ├── MV-各行各業/ 定案：衝破這片天_各行各業*.mp4；work/ 是 Canvas 2D 骨架動畫＋KTV 字幕的原始專案
│   │   │   ├── MV-流場筆觸/、MV-水墨一筆/、MV-沙畫/  各自的製作紀錄.md；work/ 放原始專案，成品在 work/video/（未定案）
│   │   │   └── 舊版/     MV-試作/（木刻、水墨試作程式與試片）
│   │   ├── 把光留給我/   教師節歌曲與生圖＋程式動畫 MV
│   │   │   ├── work/     audio/、video/、image/、workflows/、mv/（全曲 v2 來源、分鏡與驗收紀錄）
│   │   │   └── 舊版/     mv-試片/（10 秒試片）、mv-full-v1/（全曲 v1）
│   │   └── 校歌/        校歌搖滾改編（2026-10，照譜唱：OpenUtau 绮萱＋tools/sing/ 編曲）
│   │       └── work/     譜/（song.json、MIDI、OpenUtau 專案）、audio/（各版伴奏、人聲、混音）、旋律分析/、image/
│   └── 動態設計/
│       └── 動態設計作品集/ 15 秒 showreel（Canvas 2D 逐格＋Headless Edge 擷取＋numpy 配樂）
│           └── work/     reel/（Canvas 版原始專案）、hf/（HyperFrames 比較版，配樂共用）、video/
├── templates/           官方工作流程快照（Z-Image、Qwen Image Edit）、發布資訊範本.md（YouTube／Facebook／Instagram／Threads；五個媒體專案各一份、內容逐位元組相同，正本在 media-youtube-publish 的 `skills/youtube-long/references/`，改正本再整份覆蓋，不在本專案就地改）
└── scratch/             comfy-cli 回傳、節點資訊、紀錄等暫存（不進 git）
```

生成的影片、音樂、圖片（含抽幀驗收圖、字幕）產出後**從 ComfyUI 的 output 資料夾搬到該作品的 `work/`**，
分 `audio/`、`image/`、`video/`。使用者確認定案後，才把成品移到作品資料夾最上層、改名 `<作品名>.mp4`（社群壓縮版 `<作品名>_社群版.mp4`、720p `<作品名>_手機版.mp4`、歌曲 `<作品名>.mp3`）；
之前一律留在 `work/`。定稿檔的路徑記在各作品的 `製作紀錄.md`。

## 專案專屬規則

- **使用者給了譜、要求照譜照詞唱的歌（校歌、既有歌曲改編）不用 ComfyUI**，照 `docs/照譜唱歌曲流程.md`：
  旋律打成作品的 `work/譜/song.json`，用 `tools/sing/` 出 MIDI 與伴奏、OpenUtau 唱人聲；改進工具就改 `tools/sing/`，不要複製進作品資料夾。
- **ComfyUI 的操作方式與模型規則不在本專案另存一份**，一律照 `comfyui` 技能與它的 `models/` 筆記。
  實測出通用經驗就寫回 agent-setup-guide 的技能與 guide，本專案只留該片專屬的設定與決定。
- **製作流程與發布把關照 `docs/production-sop.md`**：開新作品的順序、跨作品已定案的選型、三種格式的 metadata
  清除與雙重驗證指令都在那裡。跨作品的決策定案後寫進該檔第五節，**不要在各作品的 `製作紀錄.md` 各留一份**。
  用 ComfyUI（H3）做劇情／多段影片不在本專案做，流程與定案以 `media-short-film` 的 `docs/` 為準。
- **做動畫或歌詞 MV（程式畫或生圖合成都算）前，先讀該檔第五節〈動畫／歌詞 MV 的畫面規則〉**：
  字幕位置與 KTV 掃色、坐姿要有椅子、手要碰到東西、朝向、不做危險動作等都是使用者定案的驗收條件。
- **使用者的照片、聲音、完整提示詞只放在本私有專案**，不得寫進 agent-setup-guide（公開 repo）；
  寫回技能時情境一律用通稱（例如「古裝庭院雙人短片」）。
- **社群發布文案照 [templates/發布資訊範本.md](templates/發布資訊範本.md)**：作品驗收通過後複製成 `output/<類型>/<作品名>/發布資訊.md`，依實際流程填寫 AI 揭露、工具名單與平台文案，發布後記錄公開網址。
- **對外發布的成品一律另存一份清掉 metadata 的版本**，並用 `ffprobe`（圖片看 PNG 的 `prompt` 區塊）與位元組掃描驗證
  不含 `prompt`；ComfyUI 的原始輸出檔不動。影片、**mp3**（內嵌歌詞全文）、PNG 都會帶工作流程。
- **聲音由使用者試聽**（agent 聽不到），包括台詞、參考聲音像不像、段落接點的環境音。
- 每件作品一個資料夾 `output/<類型>/<作品名>/`（作品名用中文標題），至少有 `製作紀錄.md`；`scratch/` 放暫存、不進 git。
  類型目前有 `歌曲MV`、`動態設計`；新作品不屬於這兩類再開新類型。
- **同一首歌有兩版以上 MV 時，每版開一個 `MV-<畫風>/` 子資料夾**，結構比照作品資料夾（定案成品放該子資料夾最上層、原始專案與未定案成品放它的 `work/`、自己一份 `製作紀錄.md`），
  成品檔名用 `<作品名>_<畫風>.mp4`；歌曲音檔、節拍分析等各版共用的檔案留在歌曲的 `work/`，歌曲的 `製作紀錄.md` 只記歌曲並列出各版索引。只有一版 MV 的歌不開子資料夾。
- 換電腦重現作品前，先等該作品的資料夾雲端同步完成，再調整 `local-config.json`；本機設定檔維持忽略，不提交 Git。
- 程式算圖的中間檔（上千張分鏡 PNG、配樂 wav）**放本機暫存資料夾，不要放進雲端硬碟**；專案只留腳本，成品放該作品的 `work/`，定案後移到作品資料夾最上層。
- **音訊與訊號處理只用 numpy**（例外：`tools/mv/listen.py` 用 scipy，在獨立虛擬環境跑；濾波用 FFT／STFT 自寫），不要讓作品腳本依賴 scipy：Windows 的智慧型應用程式控制會擋 scipy 的 DLL。
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
- **產出一律放 `output/`**：本專案產生的檔案或資料夾（成品、匯出、報表、生成圖、渲染等）預設放專案根目錄的 `output/`，不另開 `outputs/`、`exports/`、`generated/`、`out/` 之類的資料夾，方便找；`output/` 不進 git。部署工具指定的建置目錄（`dist/`、`build/`）不在此限。本專案每件作品一個 `output/<類型>/<作品名>/`，定案成品放最上層、工作檔放 `work/`、舊版放 `舊版/`
