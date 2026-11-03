// ★ 常改的都在這：速度、分鏡表、字幕樣式。時間一律寫「第幾小節」，不要抄秒數——換 BPM 時整支片自動跟著走。
const TL = (() => {
  const BPM = 100, INTRO_BARS = 4;            // 要跟 arrange.py、build_lyrics.py 用的一樣
  const BEAT = 60 / BPM, BAR = BEAT * 4;
  const bar = k => k * BAR;                    // 伴奏時間軸上第 k 小節（0 起）的開始秒數
  const NBARS = INTRO_BARS + 1 + 8 + 1;        // 前奏＋過門＋譜面 8 小節＋尾奏
  const DUR = 34.8;                            // 音檔長度（arrange.py 印出來的秒數，含殘響尾巴）

  // 字幕：畫面下方、小字；主歌 54px、副歌 60px（docs/production-sop.md 第五節）
  const FONT = '"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif';
  const SUBS = { y: 985, size: { verse: 54, chorus: 60 }, chorusFrom: 3 };   // 第 3 句起是副歌

  // 逐句分鏡：字面／畫面／關鍵詞（關鍵詞唱到時畫面要有變化）
  const SHOTS = [
    { id: 'S1', from: 0, to: 2, scene: 'road', name: '黎明前的原野', action: '星星一顆顆淡掉，地平線開始泛光；片名浮現' },
    { id: 'S2', from: 2, to: 5, scene: 'window', name: '還暗著的房間', action: '窗外由暗轉藍，第一道光斜斜射進來，鏡頭慢慢推近' },
    { id: 'S3', from: 5, to: 7, scene: 'window', name: '晨光爬上窗台', action: '地上的光斑一路爬上牆、爬上窗台，「台」字照亮盆栽', keys: ['光', '台'] },
    { id: 'S4', from: 7, to: 9, scene: 'window', name: '風把夢吹醒', action: '「風」字窗簾揚起；人手扶窗台，「醒」字往前上方伸懶腰', keys: ['風', '醒'], person: true },
    { id: 'S5', from: 9, to: 11, scene: 'road', name: '一起往前走', action: '大人牽著小孩走在原野上，背景往後捲，太陽在地平線下', keys: ['走'], walkers: true },
    { id: 'S6', from: 11, to: 13, scene: 'road', name: '走到天亮', action: '太陽升起、天色轉亮；「亮」字兩人停步，空著的手往前上方舉', keys: ['亮'], walkers: true },
    { id: 'S7', from: 13, to: NBARS + 0.5, scene: 'road', name: '尾奏', action: '兩人站在晨光裡，片名再出現，最後淡出', walkers: true, title: true },
  ];
  SHOTS.forEach(s => { s.start = bar(s.from); s.end = Math.min(DUR, bar(s.to)); });
  const shotAt = t => SHOTS.find(s => t < s.end) || SHOTS[SHOTS.length - 1];

  // 從字幕資料找某個字開始唱的秒數（第 n 次出現）；找不到就丟錯，免得時間軸默默變成 NaN
  function charTime(c, n = 1) {
    for (const L of window.LYRICS) for (const ch of L.chars) if (ch.c === c && --n === 0) return ch.t;
    throw new Error(`歌詞裡找不到「${c}」`);
  }

  return { BPM, BEAT, BAR, bar, DUR, FONT, SUBS, SHOTS, shotAt, charTime, TITLE: '走到天亮' };
})();
