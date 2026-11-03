// 逐格渲染 index.html 成 MP4（不需要安裝任何 npm 套件，只要 Node 18+、Edge 或 Chrome、ffmpeg）：
// 本機起一個靜態伺服器 → 無頭瀏覽器開 index.html?render → 透過 DevTools Protocol 呼叫 renderAt(t)
// → 取 canvas 的 JPEG → 餵給 ffmpeg。可以開多個瀏覽器平行渲染不同段落，最後接起來再合進音軌。
//
// 用法（在 examples/lyric-mv/ 底下）：
//   node tools/render.mjs --out <輸出.mp4> --audio <音檔> [--start 0] [--end 秒] [--workers 4] [--crf 18]
//   node tools/render.mjs --stills 3,14,20,24,30 --outdir <資料夾>    # 只輸出指定秒數的 PNG 抽查圖
//   node tools/render.mjs --check 0.25                                 # 每 0.25 秒掃一次「手構不到／手臂反折」
//   瀏覽器不在預設位置時加 --browser <路徑>
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.push([v.slice(2), arr[i + 1]]) : 0, a), []));
const FPS = 30;
const workers = parseInt(args.workers ?? '4', 10);
const crf = args.crf ?? '18';
const BROWSERS = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/microsoft-edge',
];
const browserExe = args.browser ?? BROWSERS.find(p => fs.existsSync(p));
if (!browserExe) { console.error('找不到 Edge／Chrome，請用 --browser 指定路徑'); process.exit(1); }
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lyricmv-'));

// ── 靜態伺服器 ──
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.css': 'text/css' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const pageUrl = `http://127.0.0.1:${server.address().port}/index.html?render=1`;

// ── 最小 CDP 用戶端 ──
async function openBrowser(id) {
  const udd = path.join(tmpDir, `profile-${id}`);
  const proc = spawn(browserExe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${udd}`, '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--mute-audio', '--hide-scrollbars', '--force-device-scale-factor=1',
    '--window-size=1920,1080', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((res, rej) => {
    let buf = '';
    proc.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) res(m[1]); });
    setTimeout(() => rej(new Error('瀏覽器啟動逾時')), 20000);
  });
  const port = new URL(wsUrl).port;
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(pageUrl)}`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let seq = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise(r => { const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async expr => {
    const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    if (m.error || m.result?.exceptionDetails) throw new Error(JSON.stringify(m.error || m.result.exceptionDetails).slice(0, 600));
    return m.result.result.value;
  };
  for (let i = 0; i < 300; i++) { if (await evaluate('window.READY === true').catch(() => false)) break; await new Promise(r => setTimeout(r, 100)); }
  return { evaluate, close: () => { try { ws.close(); } catch {} proc.kill(); } };
}

function ffmpegSink(file) {
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p', '-r', String(FPS), '-g', String(FPS * 2), file],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((r, j) => ff.on('close', c => c === 0 ? r() : j(new Error('ffmpeg 失敗 ' + c))));
  return {
    write: buf => new Promise(r => { if (ff.stdin.write(buf)) r(); else ff.stdin.once('drain', r); }),
    end: () => { ff.stdin.end(); return done; },
  };
}

const first = await openBrowser(0);
const DUR = await first.evaluate('window.DUR');
const start = parseFloat(args.start ?? '0'), end = Math.min(DUR, parseFloat(args.end ?? String(DUR)));

if (args.check) {
  const step = parseFloat(args.check), agg = {};
  for (let t = 0; t < DUR; t += step) {
    const m = await first.evaluate(`Rig.misses.length = 0; renderAt(${t}); JSON.stringify(Rig.misses)`);
    for (const x of JSON.parse(m)) { const k = `${x.scene}.${x.limb}`; const a = agg[k] ||= { n: 0, max: 0, first: t }; a.n++; a.max = Math.max(a.max, x.over); }
  }
  const rows = Object.entries(agg);
  console.log(rows.length ? rows.map(([k, v]) => `${k.padEnd(20)} 次數 ${String(v.n).padStart(4)}  最多差 ${v.max}px  首見 ${v.first.toFixed(2)}s`).join('\n') : '全部構得到、沒有反折');
  first.close(); server.close(); process.exit(0);
}

if (args.stills) {
  const dir = path.resolve(args.outdir ?? path.join(ROOT, 'stills')); fs.mkdirSync(dir, { recursive: true });
  for (const ts of args.stills.split(',')) {
    const url = await first.evaluate(`renderAt(${parseFloat(ts)}); document.getElementById('stage').toDataURL('image/png')`);
    const f = path.join(dir, `still_${parseFloat(ts).toFixed(2).padStart(6, '0')}.png`);
    fs.writeFileSync(f, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64')); console.log(f);
  }
  first.close(); server.close(); process.exit(0);
}

const out = path.resolve(args.out ?? path.join(ROOT, 'render.mp4'));
const f0 = Math.round(start * FPS), f1 = Math.ceil(end * FPS);
const total = f1 - f0, per = Math.ceil(total / workers);
console.log(`渲染 ${start}–${end} 秒，共 ${total} 格，${workers} 個平行程序，瀏覽器：${path.basename(browserExe)}`);
const t0 = Date.now(); let doneFrames = 0;
const segs = [];
await Promise.all(Array.from({ length: workers }, async (_, w) => {
  const a = f0 + w * per, b = Math.min(f1, a + per); if (a >= b) return;
  const seg = path.join(tmpDir, `seg_${String(w).padStart(2, '0')}.mp4`); segs[w] = seg;
  const br = w === 0 ? first : await openBrowser(w);
  const sink = ffmpegSink(seg);
  for (let f = a; f < b; f++) {
    const url = await br.evaluate(`renderAt(${(f / FPS).toFixed(6)}); document.getElementById('stage').toDataURL('image/jpeg', 0.95)`);
    await sink.write(Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
    if (++doneFrames % 150 === 0) { const s = (Date.now() - t0) / 1000; console.log(`  ${doneFrames}/${total} 格，${(doneFrames / s).toFixed(1)} 格/秒`); }
  }
  await sink.end(); br.close();
}));
server.close();

// 接段落 → 合音軌（-map_metadata -1：不帶任何來源 metadata）
const list = path.join(tmpDir, 'list.txt');
fs.writeFileSync(list, segs.filter(Boolean).map(s => `file '${s.replace(/\\/g, '/')}'`).join('\n'));
const run = a => new Promise((r, j) => spawn('ffmpeg', a, { stdio: 'inherit' }).on('close', c => c === 0 ? r() : j(new Error('ffmpeg ' + a.join(' ')))));
const video = path.join(tmpDir, 'video.mp4');
await run(['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', video]);
if (args.audio) {
  await run(['-y', '-v', 'error', '-i', video, '-ss', String(start), '-t', String(f1 / FPS - start), '-i', args.audio,
    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-map_metadata', '-1', '-movflags', '+faststart', out]);
} else {
  fs.copyFileSync(video, out);
}
setTimeout(() => { try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {} }, 1500);
console.log(`完成：${out}（${((Date.now() - t0) / 1000).toFixed(0)} 秒）`);
