# 畫風庫（參考資料）

做歌詞 MV 選畫風時查這裡。這些是**只借畫法的參考**，不是流程：字幕、人物、動作規則一律以 `docs/production-sop.md` 第五節為準，衝突時 SOP 優先。

## 怎麼用

1. 查索引：`lemo-opuscar/INDEX.md`、`huashu-art-motion/references/风格配方/INDEX.md`，以及本專案自寫的 `本專案/`（水墨一筆、沙畫）。
2. 依歌的年代、情緒與要畫的東西，挑 3–5 個給使用者選。
3. 讀該畫風的說明，把色板、材質、線條、鏡頭、動作節奏寫進作品的 `製作紀錄.md`。
4. 用過的畫風在 `製作紀錄.md` 與 `發布資訊.md` 署名出處。

只借規則與畫法，不搬樣片的故事、角色、構圖。文件保留上游原文（lemo 多為英文，huashu 為簡體）；唯一的改動是下面「已移除」的內容，更新版本時要重新移除。

## 來源

| 資料夾 | 上游 | 版本 | 授權 |
|---|---|---|---|
| `lemo-opuscar/` | [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | `bebbbe1` | MIT（見資料夾 LICENSE） |
| `huashu-art-motion/` | [alchaincyf/huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | `8a0d7d7` | MIT（見資料夾 LICENSE） |

署名寫法：「畫風參考 LemoLab lemo-opuscar 的 <畫風名>（MIT）」、「畫風參考 花叔 huashu-art-motion 的 <畫風名>（MIT）」。

## 本專案自寫的畫風（`本專案/`）

上游沒有、在本專案做出來的畫風，畫法和使用者定案的規則寫在這裡，下一首歌可以直接選。程式留在首次使用的作品資料夾，筆記寫明位置。

| 畫風 | 筆記 | 首次使用 |
|---|---|---|
| 水墨一筆 | [本專案/水墨一筆.md](本專案/水墨一筆.md) | 〈衝破這片天〉MV-水墨一筆（2026-11） |
| 沙畫 | [本專案/沙畫.md](本專案/沙畫.md) | 〈衝破這片天〉MV-沙畫（2026-11） |

流場筆觸用的是上游 huashu-art-motion 的 `09_postimp`，不另寫筆記；本專案的用法見〈衝破這片天〉`MV-流場筆觸/製作紀錄.md`。

## 搬了什麼

- **lemo-opuscar**：66 種畫風的 `STYLE.md`、`DEMO.md`、`style.json`，索引改名 `INDEX.md`。
- **huashu-art-motion**：`references/` 的文字，以及 `lib/` 的 `util.js`、`paint.js`、`rig.js`（已逐行讀過）。`rig.js` 綁定上游的少女與貓角色，通用的只有 `ik2`、`limb`、`smooth`、`taper`。

## 刻意沒搬

- 上游的 `CLAUDE.md`、`AGENTS.md`、`SKILL.md`：會蓋過本專案的流程，**不要補回來**。
- 所有樣片、圖片、字型、配音、音樂、下載與渲染工具，以及 `poster.jpg`（靜幀屬 CC BY 4.0）。

## 已移除

有疑慮的內容不留在本庫，**不要補回來**：

- 點名公司、作品或在世藝術家的配方：`25_ghibli`、`27_kirby`、`35_shinkai`、`37_rick_morty`、`52_south_park`、`53_pixar`、`21_kusama`。
- 作品可能仍受著作權保護的藝術家配方：`13_pop`、`23_dali`、`24_hopper`、`31_haring`、`36_picasso_blue`、`49_chagall`。
- `huashu-art-motion/references/` 裡提到以上任一項的整行文字（含索引），所以部分表格與段落比上游短。

lemo-opuscar 的 `STYLE.md` 仍會以「grammar only」列出參考作品（如 *Paper Mario*、Apple 發表會、Saul Bass），只借語法，不要模仿具體作品，也不要把這些名稱寫進對外文案。
