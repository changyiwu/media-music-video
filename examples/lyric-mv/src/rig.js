// 2D 人物骨架：正向運動學（關節角度）＋兩段式 IK（手指定目標點），畫成一體成形的實心剪影。
// 座標 y 向下；角色面向 f（+1 向右、-1 向左）。長度單位是「身高比例」，乘上 s（像素）才是畫面大小。
//
// pose = {
//   x, y : 髖關節位置（像素）   s : 身高（像素）   f : 面向   lean : 軀幹前傾（弧度）   build : 胖瘦（1＝標準）
//   sh:[遠, 近] 上臂角度（從正下方往前轉為正，π＝舉到頭頂）   el:[遠, 近] 手肘彎曲（前臂往前上轉為正）
//   hp:[遠, 近] 大腿角度（從正下方往前為正）                 kn:[遠, 近] 膝蓋彎曲（小腿往後為正）
//   ik : { handF, handN }  手要碰到的位置（像素），會覆蓋上面的手臂角度
//   cap : 戴帽子（剪影一眼分得出誰是誰）
// }
const Rig = (() => {
  const P = { T: 0.30, N: 0.045, HR: 0.068, UA: 0.165, FA: 0.155, TH: 0.245, SH: 0.24,
    wTop: 0.15, wBot: 0.12, wUA: 0.07, wFA: 0.06, wTH: 0.1, wSH: 0.075 };
  const V = a => [Math.sin(a), Math.cos(a)];
  const misses = [];   // 構不到的 IK 目標（tools/render.mjs --check 用來找「手沒碰到東西」）
  let label = '';

  function ik(a, t, l1, l2, bend, limb) {
    let dx = t[0] - a[0], dy = t[1] - a[1], d = Math.hypot(dx, dy);
    const maxd = (l1 + l2) * 0.999;
    if (d > maxd + 4) misses.push({ scene: label, limb, over: Math.round(d - maxd) });
    if (d > maxd) { dx *= maxd / d; dy *= maxd / d; d = maxd; }
    d = Math.max(d, 1e-4);
    const A = Math.acos(E.clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1));
    const ang = Math.atan2(dy, dx) + bend * A;
    return [[a[0] + Math.cos(ang) * l1, a[1] + Math.sin(ang) * l1], [a[0] + dx, a[1] + dy]];
  }

  function solve(p) {
    const s = p.s, f = p.f || 1, lean = p.lean || 0;
    const W = q => [p.x + f * q[0] * s, p.y + q[1] * s];
    const up = [Math.sin(lean), -Math.cos(lean)];
    const sh = [up[0] * P.T, up[1] * P.T], nk = [sh[0] + up[0] * P.N, sh[1] + up[1] * P.N];
    const hd = [nk[0] + up[0] * P.HR, nk[1] + up[1] * P.HR];
    const arm = (a, e) => { const A = lean + a, v = V(A), el = [sh[0] + v[0] * P.UA, sh[1] + v[1] * P.UA], v2 = V(A + e); return [W(el), W([el[0] + v2[0] * P.FA, el[1] + v2[1] * P.FA])]; };
    const leg = (h, k) => { const v = V(h), kn = [v[0] * P.TH, v[1] * P.TH], v2 = V(h - k); return [W(kn), W([kn[0] + v2[0] * P.SH, kn[1] + v2[1] * P.SH])]; };
    const sa = p.sh || [0, 0], ea = p.el || [0, 0], ha = p.hp || [0, 0], ka = p.kn || [0, 0];
    const J = { s, f, lean, build: p.build || 1, cap: p.cap, hip: W([0, 0]), sh: W(sh), neck: W(nk), head: W(hd) };
    [J.elF, J.handF] = arm(sa[0], ea[0]); [J.elN, J.handN] = arm(sa[1], ea[1]);
    [J.knF, J.footF] = leg(ha[0], ka[0]); [J.knN, J.footN] = leg(ha[1], ka[1]);
    const k = p.ik || {};
    if (k.handF) [J.elF, J.handF] = ik(J.sh, k.handF, P.UA * s, P.FA * s, f, 'handF');
    if (k.handN) [J.elN, J.handN] = ik(J.sh, k.handN, P.UA * s, P.FA * s, f, 'handN');
    // 檢查：手舉到肩膀以上卻在身體後方（規則：手不可以往身後反折）
    for (const [nm, h] of [['handF', J.handF], ['handN', J.handN]]) {
      if ((h[0] - J.sh[0]) * f < -0.12 * s && J.sh[1] - h[1] > -0.05 * s) misses.push({ scene: label, limb: nm + '反折身後', over: 0 });
    }
    return J;
  }

  // 讓較低的那隻腳踩在地面 y 上（走路時髖部會自然上下起伏）
  function plant(p, groundY) {
    const J = solve({ ...p, ik: {} });
    return { ...p, y: p.y + groundY - Math.max(J.footF[1], J.footN[1]) };
  }

  function seg(ctx, a, b, w) { ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }

  // 實心剪影：四肢、軀幹、脖子、頭用同一個顏色畫，連成一體（規則：頭和脖子不可以分開畫）
  function draw(ctx, J, color) {
    const s = J.s, b = J.build;
    ctx.save();
    ctx.fillStyle = ctx.strokeStyle = color; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    seg(ctx, J.hip, J.knF, P.wTH * s * b); seg(ctx, J.knF, J.footF, P.wSH * s);
    seg(ctx, J.sh, J.elF, P.wUA * s); seg(ctx, J.elF, J.handF, P.wFA * s);
    // 軀幹：肩寬、腰窄的四邊形
    const dx = J.sh[0] - J.hip[0], dy = J.sh[1] - J.hip[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
    const wt = P.wTop * s * b / 2, wb = P.wBot * s * b / 2;
    ctx.beginPath();
    ctx.moveTo(J.sh[0] + nx * wt, J.sh[1] + ny * wt); ctx.lineTo(J.sh[0] - nx * wt, J.sh[1] - ny * wt);
    ctx.lineTo(J.hip[0] - nx * wb, J.hip[1] - ny * wb); ctx.lineTo(J.hip[0] + nx * wb, J.hip[1] + ny * wb);
    ctx.closePath(); ctx.fill();
    seg(ctx, J.sh, J.head, P.HR * s * 0.9);                       // 脖子連到頭
    ctx.beginPath(); ctx.arc(J.head[0], J.head[1], P.HR * s, 0, Math.PI * 2); ctx.fill();
    if (J.cap) {   // 鴨舌帽：帽簷朝面向
      ctx.beginPath(); ctx.arc(J.head[0], J.head[1] - P.HR * s * 0.15, P.HR * s * 1.08, Math.PI, 0); ctx.fill();
      ctx.fillRect(J.head[0] + (J.f > 0 ? 0 : -P.HR * s * 1.9), J.head[1] - P.HR * s * 0.3, P.HR * s * 1.9, P.HR * s * 0.28);
    }
    seg(ctx, J.hip, J.knN, P.wTH * s * b); seg(ctx, J.knN, J.footN, P.wSH * s);
    seg(ctx, J.sh, J.elN, P.wUA * s); seg(ctx, J.elN, J.handN, P.wFA * s);
    for (const ft of [J.footF, J.footN]) seg(ctx, ft, [ft[0] + J.f * 0.07 * s, ft[1]], 0.045 * s);   // 腳掌朝前
    ctx.restore();
  }

  return { solve, plant, draw, misses, setLabel: l => { label = l; } };
})();
