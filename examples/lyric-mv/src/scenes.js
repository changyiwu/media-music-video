// 兩個場景（原野、窗邊）＋片名與導演層。每個函式只看時間 t，任何一格都能單獨算出來。
const Scenes = (() => {
  const W = 1920, H = 1080;

  // ── 天色：0＝夜、0.5＝黎明、1＝白天；兩個場景共用，跨場景切換時天色是連續的 ──
  const dayAt = t => E.track([[0, 0], [TL.bar(2), 0.18], [TL.bar(9), 0.42], [TL.bar(11), 0.55], [TL.bar(12.5), 1]], t);
  const SKY = { night: [[12, 14, 40], [44, 32, 74]], dawn: [[70, 92, 160], [255, 158, 112]], day: [[112, 172, 232], [255, 226, 184]] };
  function skyColors(d) {
    const [a, b, u] = d < 0.5 ? [SKY.night, SKY.dawn, d / 0.5] : [SKY.dawn, SKY.day, (d - 0.5) / 0.5];
    return [0, 1].map(i => a[i].map((v, k) => E.lerp(v, b[i][k], u)));
  }
  function sky(ctx, t, x, y, w, h) {
    const [top, bot] = skyColors(dayAt(t)), g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, E.rgba(top)); g.addColorStop(1, E.rgba(bot));
    ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  }
  // 太陽高度：「天」「亮」之前都在地平線下
  const sunUp = t => E.track([[TL.bar(10.5), -0.08], [TL.bar(12), 0.12], [TL.bar(14.5), 0.3]], t);

  // ── 原野：遠山、近丘、地面往後捲，大人牽小孩往右走 ──
  const HORIZON = 700, GROUND = 840;
  let walk = null;
  function walkTables() {
    // 「亮」字開始停步；速度、步伐相位都用積分，停下來時不會跳格
    const stop = TL.charTime('亮');
    const amp = t => 1 - E.smooth(E.prog(t, stop, stop + 0.7));
    return {
      amp, stop,
      scroll: E.integrate(t => 290 * amp(t), TL.DUR),
      phA: E.integrate(t => 2 * Math.PI / (TL.BEAT * 2) * amp(t), TL.DUR),     // 大人兩拍一個循環
      phC: E.integrate(t => 2 * Math.PI / (TL.BEAT * 1.5) * amp(t), TL.DUR),   // 小孩步子小、腳步快
    };
  }

  function hills(ctx, off, base, amp, freq, color, seed) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(0, H);
    for (let x = 0; x <= W; x += 16) ctx.lineTo(x, base - amp * (0.6 + 0.4 * E.noise((x + off) * freq + seed)) - amp * 0.3 * E.noise((x + off) * freq * 3 + seed * 2));
    ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
  }

  function road(ctx, t, shot) {
    walk ||= walkTables();
    const d = dayAt(t), sc = walk.scroll(t);
    sky(ctx, t, 0, 0, W, HORIZON + 40);
    // 星星：天一亮就淡掉，每顆淡掉的時間不同
    for (let i = 0; i < 90; i++) {
      const a = E.clamp(1 - d * 3.2 - E.rand(i, 3) * 0.4) * (0.6 + 0.4 * Math.sin(t * 2 + i));
      if (a <= 0) continue;
      ctx.fillStyle = `rgba(255,250,235,${a})`;
      ctx.fillRect(E.rand(i) * W, E.rand(i, 1) * HORIZON * 0.8, 2.5, 2.5);
    }
    // 太陽與光暈（副歌每一拍輕輕脈動）
    const sy = HORIZON - sunUp(t) * 900, beat = (t / TL.BEAT) % 1;
    const pulse = t > TL.bar(9) ? Math.exp(-beat * 5) * 0.25 : 0;
    const glow = ctx.createRadialGradient(1380, sy, 0, 1380, sy, 520 * (1 + pulse));
    glow.addColorStop(0, `rgba(255,236,190,${0.25 + 0.6 * d})`); glow.addColorStop(1, 'rgba(255,200,150,0)');
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, HORIZON + 40);
    ctx.fillStyle = '#fff3d6'; ctx.beginPath(); ctx.arc(1380, sy, 62, 0, Math.PI * 2); ctx.fill();
    // 遠山、近丘（視差：越遠捲得越慢），地面
    const shade = k => E.rgba([E.lerp(20, 70, d * k), E.lerp(18, 60, d * k), E.lerp(36, 70, d * k)]);
    hills(ctx, sc * 0.08, HORIZON + 10, 90, 0.004, shade(0.9), 1);
    hills(ctx, sc * 0.3, HORIZON + 70, 60, 0.007, shade(0.6), 7);
    ctx.fillStyle = shade(0.35); ctx.fillRect(0, GROUND, W, H - GROUND);
    // 地上的草叢跟著腳步速度往後捲，腳才不會像在溜冰
    ctx.strokeStyle = shade(0.35); ctx.lineWidth = 4; ctx.lineCap = 'round';
    for (let i = -2; i < 26; i++) {
      const base = i * 90 - (sc % 90), r = E.rand(Math.floor(sc / 90) + i, 5);
      for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.moveTo(base + k * 9, GROUND + 2); ctx.lineTo(base + k * 12 - 6 + r * 10, GROUND - 14 - r * 22); ctx.stroke(); }
    }
    if (shot.walkers) walkers(ctx, t);
  }

  function walkPose(s, ph, amp, x, y, extra) {
    const A = 0.42 * amp, sw = Math.sin(ph), c = Math.cos(ph);
    return { x, y, s, f: 1, lean: 0.05 * amp,
      hp: [A * sw, -A * sw], kn: [0.08 + 0.6 * Math.max(0, c) * amp, 0.08 + 0.6 * Math.max(0, -c) * amp],
      sh: [-0.35 * sw * amp, 0.35 * sw * amp], el: [0.3, 0.25], ...extra };
  }

  function walkers(ctx, t) {
    const amp = walk.amp(t), ink = 'rgba(16,12,22,1)';
    // 小孩在大人左後方、離鏡頭較近（地面低一點）；身高比 1.6
    let A = Rig.plant(walkPose(450, walk.phA(t), amp, 870, 0), GROUND - 4);
    let C = Rig.plant(walkPose(280, walk.phC(t) + 1.3, amp, 735, 0, { cap: true, build: 0.9 }), GROUND + 26);
    // 牽手：兩人的肩膀連線上找一個兩邊都構得到的點
    const JA = Rig.solve(A), JC = Rig.solve(C);
    const dx = JC.sh[0] - JA.sh[0], dy = JC.sh[1] - JA.sh[1], dist = Math.hypot(dx, dy);
    const armA = 0.32 * 450, armC = 0.32 * 280;   // 手臂長（上臂＋前臂）
    const k = Math.max(dist - 0.9 * armC, Math.min(0.88 * armA, dist - 0.5 * armC)) / dist, hold = [JA.sh[0] + dx * k, JA.sh[1] + dy * k];
    // 「亮」：空著的手往前上方舉起，小孩先、大人慢半拍（不左右鏡像）
    const raise = dl => E.easeOut(E.prog(t, walk.stop + dl, walk.stop + dl + 0.8));
    const rA = raise(0.25), rC = raise(0);
    const freeA = Rig.solve({ ...A, sh: [E.lerp(A.sh[0], 2.45, rA), 0], el: [E.lerp(0.3, 0.2, rA), 0] }).handF;
    const freeC = Rig.solve({ ...C, sh: [0, E.lerp(C.sh[1], 2.7, rC)], el: [0, E.lerp(0.25, 0.35, rC)] }).handN;
    Rig.draw(ctx, Rig.solve({ ...A, ik: { handN: hold, handF: freeA } }), ink);
    Rig.draw(ctx, Rig.solve({ ...C, ik: { handF: hold, handN: freeC } }), ink);
  }

  // ── 窗邊：還暗的房間，光從窗戶進來、爬上窗台；窗簾被風吹起；人扶著窗台，「醒」字伸懶腰 ──
  const WIN = { x: 1040, y: 170, w: 480, h: 430 }, SILL = WIN.y + WIN.h, FLOOR = 900;

  function room(ctx, t, shot) {
    const d = dayAt(t), lit = E.clamp(d * 1.6);
    // 鏡頭：S2 S3 慢慢推近窗戶，S4 切近景
    const zoom = shot.id === 'S4' ? 1.2 + 0.03 * E.prog(t, shot.start, shot.end) : E.track([[TL.bar(2), 1], [TL.bar(7), 1.14]], t);
    const fx = shot.id === 'S4' ? 1080 : 1180, fy = shot.id === 'S4' ? 520 : 520;
    ctx.save();
    ctx.translate(W / 2, H / 2); ctx.scale(zoom, zoom); ctx.translate(-fx, -fy);
    // 牆、地板
    ctx.fillStyle = E.rgba([E.lerp(22, 92, lit), E.lerp(20, 74, lit), E.lerp(34, 70, lit)]); ctx.fillRect(-200, -200, W + 400, FLOOR + 200);
    ctx.fillStyle = E.rgba([E.lerp(16, 70, lit), E.lerp(13, 52, lit), E.lerp(20, 44, lit)]); ctx.fillRect(-200, FLOOR, W + 400, H);
    // 窗外：天色與遠山
    ctx.save(); ctx.beginPath(); ctx.rect(WIN.x, WIN.y, WIN.w, WIN.h); ctx.clip();
    sky(ctx, t, WIN.x, WIN.y, WIN.w, WIN.h);
    hills(ctx, 0, SILL - 40, 50, 0.01, E.rgba([E.lerp(20, 80, d), E.lerp(18, 70, d), E.lerp(36, 80, d)]), 3);
    ctx.restore();
    // 光束：第一道光斜斜射進房間
    const beam = E.track([[TL.bar(3.2), 0], [TL.bar(5), 0.35], [TL.bar(9), 0.55]], t);
    if (beam > 0) {
      const g = ctx.createLinearGradient(WIN.x, WIN.y, 500, FLOOR);
      g.addColorStop(0, `rgba(255,214,150,${beam})`); g.addColorStop(1, 'rgba(255,200,140,0)');
      ctx.fillStyle = g; ctx.beginPath();
      ctx.moveTo(WIN.x, WIN.y + 40); ctx.lineTo(WIN.x + WIN.w * 0.6, WIN.y + 20); ctx.lineTo(760, FLOOR + 60); ctx.lineTo(260, FLOOR + 60);
      ctx.closePath(); ctx.fill();
    }
    // 光斑「爬」：地板 → 牆腳 → 窗台（「光」字開始，「台」字到達）
    const t0 = TL.charTime('光'), t1 = TL.charTime('台');
    if (t > t0 - 0.5) {
      const u = E.smooth(E.prog(t, t0, t1));
      const path = [[560, FLOOR + 50], [1000, FLOOR - 10], [1000, SILL + 120], [1200, SILL - 6]];
      const seg = Math.min(2, Math.floor(u * 3)), v = u * 3 - seg, p = path[seg].map((c, i) => E.lerp(c, path[seg + 1][i], v));
      const a = 0.55 * E.prog(t, t0 - 0.5, t0);
      const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], 120);
      g.addColorStop(0, `rgba(255,226,160,${a})`); g.addColorStop(1, 'rgba(255,210,150,0)');
      ctx.fillStyle = g; ctx.fillRect(p[0] - 130, p[1] - 130, 260, 260);
    }
    // 窗框、窗台、盆栽（「台」字被照亮）
    ctx.strokeStyle = E.rgba([E.lerp(40, 150, lit), E.lerp(34, 120, lit), E.lerp(40, 100, lit)]); ctx.lineWidth = 18;
    ctx.strokeRect(WIN.x, WIN.y, WIN.w, WIN.h);
    ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(WIN.x + WIN.w / 2, WIN.y); ctx.lineTo(WIN.x + WIN.w / 2, SILL); ctx.stroke();
    ctx.fillStyle = ctx.strokeStyle; ctx.fillRect(WIN.x - 30, SILL, WIN.w + 60, 26);
    const potLit = E.smooth(E.prog(t, TL.charTime('台'), TL.charTime('台') + 0.8));
    ctx.fillStyle = E.rgba([E.lerp(40, 200, potLit), E.lerp(28, 120, potLit), E.lerp(30, 80, potLit)]);
    ctx.beginPath(); ctx.moveTo(1380, SILL); ctx.lineTo(1372, SILL - 56); ctx.lineTo(1448, SILL - 56); ctx.lineTo(1440, SILL); ctx.fill();
    ctx.strokeStyle = E.rgba([E.lerp(20, 90, potLit), E.lerp(36, 170, potLit), E.lerp(24, 80, potLit)]); ctx.lineWidth = 7;
    for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(1410, SILL - 56); ctx.quadraticCurveTo(1395 + i * 12, SILL - 110, 1380 + i * 22, SILL - 140 + (i % 2) * 20); ctx.stroke(); }
    // 床（「夢」：這個人剛從床上起來）
    ctx.fillStyle = E.rgba([E.lerp(30, 120, lit), E.lerp(28, 100, lit), E.lerp(44, 110, lit)]);
    ctx.fillRect(180, 760, 560, 90); ctx.fillRect(180, 640, 36, 260); ctx.fillRect(704, 850, 36, 50); ctx.fillRect(216, 850, 30, 50);
    ctx.fillStyle = E.rgba([E.lerp(40, 170, lit), E.lerp(38, 150, lit), E.lerp(60, 160, lit)]);
    ctx.beginPath(); ctx.moveTo(300, 760); ctx.quadraticCurveTo(500, 720, 740, 770); ctx.lineTo(740, 800); ctx.lineTo(300, 800); ctx.fill();
    curtain(ctx, t, lit);
    if (shot.person) person(ctx, t);
    ctx.restore();
  }

  // 窗簾：「風」字被吹起，之後慢慢落回
  function curtain(ctx, t, lit) {
    const tw = TL.charTime('風'), gust = E.easeOut(E.prog(t, tw, tw + 0.5)) * Math.exp(-Math.max(0, t - tw - 0.5) * 0.6);
    const sway = 0.15 + gust;
    ctx.fillStyle = E.rgba([E.lerp(50, 210, lit), E.lerp(40, 170, lit), E.lerp(60, 150, lit)], 0.92);
    ctx.beginPath(); ctx.moveTo(WIN.x - 40, WIN.y - 20);
    ctx.lineTo(WIN.x + 110, WIN.y - 20);
    for (let k = 0; k <= 10; k++) {
      const yy = WIN.y - 20 + k * (WIN.h + 50) / 10, lift = (k / 10) ** 2;
      ctx.lineTo(WIN.x + 110 + sway * 160 * lift + 14 * Math.sin(t * 3 + k) * sway, yy - sway * 80 * lift);
    }
    ctx.lineTo(WIN.x - 40, SILL + 30); ctx.closePath(); ctx.fill();
  }

  function person(ctx, t) {
    const tw = TL.charTime('醒'), r = E.easeOut(E.prog(t, tw, tw + 0.9));
    const p = Rig.plant({ x: 985, y: 0, s: 470, f: 1, lean: E.lerp(0.06, -0.05, r), sh: [0.15, 0], el: [0.3, 0], hp: [0.05, -0.08], kn: [0.05, 0.1] }, FLOOR);
    // 伸懶腰：兩手往前上方，高低不同（不鏡像）
    const up = Rig.solve({ ...p, sh: [2.45, 2.75], el: [0.15, 0.3] });
    const rest = Rig.solve(p);
    const sill = [WIN.x + 10, SILL - 2];
    const hN = [E.lerp(sill[0], up.handN[0], r), E.lerp(sill[1], up.handN[1], r)];
    const hF = [E.lerp(rest.handF[0], up.handF[0], E.prog(r, 0.15, 1)), E.lerp(rest.handF[1], up.handF[1], E.prog(r, 0.15, 1))];
    Rig.draw(ctx, Rig.solve({ ...p, ik: { handN: hN, handF: hF } }), 'rgba(14,10,20,1)');
  }

  // ── 片名：字型疊在畫面上，加描邊，暗處亮處都看得清楚 ──
  function title(ctx, t) {
    const show = (a, b) => E.smooth(E.prog(t, a, a + 0.8)) * (1 - E.smooth(E.prog(t, b - 0.8, b)));
    const alpha = Math.max(show(0.6, TL.bar(2) - 0.2), show(TL.bar(13) + 0.3, TL.DUR + 1));
    if (alpha <= 0) return;
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.font = `900 132px ${TL.FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
    ctx.lineWidth = 16; ctx.strokeStyle = 'rgba(10,8,18,0.7)'; ctx.strokeText(TL.TITLE, W / 2, 220);
    ctx.fillStyle = '#fff6e6'; ctx.fillText(TL.TITLE, W / 2, 220);
    ctx.restore();
  }

  function draw(ctx, t) {
    const shot = TL.shotAt(t);
    Rig.setLabel(shot.id);
    (shot.scene === 'road' ? road : room)(ctx, t, shot);
    title(ctx, t);
    Subs.draw(ctx, t);
    // 進副歌的閃光；結尾 1.2 秒淡出到黑
    const flash = Math.exp(-Math.max(0, t - TL.bar(9)) * 6) * (t >= TL.bar(9) ? 0.6 : 0);
    if (flash > 0.01) { ctx.fillStyle = `rgba(255,244,220,${flash})`; ctx.fillRect(0, 0, W, H); }
    const out = E.prog(t, TL.DUR - 1.2, TL.DUR);
    if (out > 0) { ctx.fillStyle = `rgba(0,0,0,${out})`; ctx.fillRect(0, 0, W, H); }
  }

  return { draw };
})();
