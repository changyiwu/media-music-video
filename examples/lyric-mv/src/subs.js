// 歌詞字幕：畫面下方、字級收小、同一時間只有一句；KTV 效果——唱到哪裡，白字就由左到右掃成暖金色（長音掃得慢）。
const Subs = (() => {
  const cache = new Map();
  function layout(ctx, L, i) {
    if (cache.has(L.id)) return cache.get(L.id);
    const S = i + 1 >= TL.SUBS.chorusFrom ? TL.SUBS.size.chorus : TL.SUBS.size.verse;
    ctx.save(); ctx.font = `800 ${S}px ${TL.FONT}`;
    const widths = L.chars.map(c => ctx.measureText(c.c).width + S * 0.08);
    ctx.restore();
    const total = widths.reduce((a, b) => a + b, 0), xs = [];
    let x = 960 - total / 2;
    widths.forEach(w => { xs.push(x + w / 2); x += w; });
    const r = { S, xs }; cache.set(L.id, r); return r;
  }
  function draw(ctx, t) {
    window.LYRICS.forEach((L, i) => {
      if (t < L.start || t > L.end) return;
      const { S, xs } = layout(ctx, L, i), y = TL.SUBS.y;
      const alpha = E.smooth(E.prog(t, L.start, L.start + 0.25)) * (1 - E.smooth(E.prog(t, L.end - 0.25, L.end)));
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.font = `800 ${S}px ${TL.FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
      L.chars.forEach((c, j) => {
        const x = xs[j], w = ctx.measureText(c.c).width;
        ctx.lineWidth = S * 0.16; ctx.strokeStyle = 'rgba(6,4,10,0.75)'; ctx.strokeText(c.c, x, y);
        ctx.fillStyle = '#f6f2ec'; ctx.fillText(c.c, x, y);
        const p = E.clamp((t - c.t) / Math.max(0.08, c.e - c.t));   // 這個字唱了幾成
        if (p > 0) {
          ctx.save(); ctx.beginPath(); ctx.rect(x - w / 2 - 2, y - S, w * p + 2 + (p >= 1 ? 4 : 0), S * 2); ctx.clip();
          ctx.fillStyle = '#ffc460'; ctx.fillText(c.c, x, y);
          ctx.restore();
        }
      });
      ctx.restore();
    });
  }
  return { draw };
})();
