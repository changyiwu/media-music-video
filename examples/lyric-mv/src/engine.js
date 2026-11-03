// 共用小工具：緩動、關鍵影格、可重現的亂數、積分表。
// 所有畫面都是「時間 t 的純函數」——任意一格可以單獨算出來，才能拖時間軸預覽、多開平行渲染。
const E = (() => {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = t => { t = clamp(t); return t * t * (3 - 2 * t); };
  const easeOut = t => 1 - Math.pow(1 - clamp(t), 3);
  const easeIn = t => Math.pow(clamp(t), 3);
  const prog = (t, a, b) => clamp((t - a) / (b - a));

  // 關鍵影格：keys = [[秒, 值], ...]；值可以是數字或數字陣列（顏色）。兩點之間用 smoothstep。
  function track(keys, t, ease = smooth) {
    if (t <= keys[0][0]) return keys[0][1];
    const n = keys.length;
    if (t >= keys[n - 1][0]) return keys[n - 1][1];
    let i = 0; while (keys[i + 1][0] <= t) i++;
    const [t0, v0] = keys[i], [t1, v1] = keys[i + 1], u = ease((t - t0) / (t1 - t0));
    return Array.isArray(v0) ? v0.map((v, k) => lerp(v, v1[k], u)) : lerp(v0, v1, u);
  }

  // 可重現的雜湊亂數（同一個 i 永遠得到同一個值）
  function hash(n) { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453123; return x - Math.floor(x); }
  const rand = (i, k = 0) => hash(i * 12.9898 + k * 78.233 + 0.5);
  function noise(x) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u) * 2 - 1; }

  // 把速度曲線積分成位置表（捲動距離、走路相位），查表內插；速度會變也不會跳格
  function integrate(fn, dur, hz = 240) {
    const n = Math.ceil(dur * hz) + 3, arr = new Float64Array(n);
    let acc = 0;
    for (let i = 0; i < n; i++) { arr[i] = acc; acc += fn((i + 0.5) / hz) / hz; }
    return t => { const x = clamp(t * hz, 0, n - 1.001), i = Math.floor(x); return arr[i] + (arr[i + 1] - arr[i]) * (x - i); };
  }

  const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

  return { clamp, lerp, smooth, easeOut, easeIn, prog, track, rand, noise, integrate, rgba };
})();
