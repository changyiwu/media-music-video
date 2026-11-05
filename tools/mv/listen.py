"""節拍分析（media-music-video）：只採用這裡的拍點、小節；段落標籤與逐字時間不採用。

來源：Yari-tuber/mv-director commit 79af43a 的 scripts/listen.py（MIT，見同資料夾 LICENSE）。
本專案改動：拿掉強制對齊（align.py）。其餘維持上游程式，方便對照。

上游說明如下。
mv-director 第 1 步 · 听歌拆解：把一首歌拆成做 MV 用得上的数据。

用法（在项目文件夹里跑，或者用 --out 指定）：
  python -I listen.py <歌.mp3/wav> --lrc 歌词.lrc [--start 13 --end 58] [--vocals 人声.wav] [--inst 伴奏.wav] [--bpm 99] [--out .]

产出（都写进 --out）：
  song.json    节拍、小节、段落、能量曲线、鼓点、大时刻候选、歌词（逐字时间）。时间全是「片内秒」：0 = --start。
  song.md      拆解表：段落、大时刻候选、逐小节表、歌词。模型和人都先读这个。
  songmap.png  一张图看整段：能量、小节线、段落、歌词、大时刻候选。
  audio.wav    切好的这一段（48 kHz 立体声，按采样精确切，结尾淡出）。成片就配这条。

只用 numpy / scipy / matplotlib：不用 librosa（Windows 上 numba 会直接崩掉进程）。
有分离好的人声（demucs 的 vocals.wav）就传 --vocals：逐字时间更准；有伴奏（no_vocals.wav）传 --inst：鼓点更干净。
"""
import argparse, json, math, re, shutil, subprocess, sys
from pathlib import Path

import numpy as np
from scipy import ndimage, signal

SR, HOP, NFFT = 24000, 240, 2048       # 100 帧/秒 → 10 ms 一格
FPS = SR / HOP
OUT_FPS = 60                           # 能量曲线按 60 帧/秒存，和成片一一对应


def ffmpeg_bin():
    f = shutil.which('ffmpeg')
    if f: return f
    sys.exit('找不到 ffmpeg：先装 ffmpeg 并放进 PATH')


FF = ffmpeg_bin()


def load(path, sr=SR):
    raw = subprocess.run([FF, '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def stft_mag(y):
    y = np.pad(y, (NFFT // 2, NFFT // 2))
    fr = np.lib.stride_tricks.sliding_window_view(y, NFFT)[::HOP]
    win = np.hanning(NFFT).astype(np.float32)
    S = np.empty((len(fr), NFFT // 2 + 1), np.float32)
    for i in range(0, len(fr), 1500):
        S[i:i + 1500] = np.abs(np.fft.rfft(fr[i:i + 1500] * win, axis=1))
    return S


def mel_bank(nb=72, fmin=30.0, fmax=11500.0):
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    f = mel2hz(np.linspace(hz2mel(fmin), hz2mel(fmax), nb + 2))
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    fb = np.zeros((nb, len(freqs)), np.float32)
    for i in range(nb):
        l, c, r = f[i], f[i + 1], f[i + 2]
        fb[i] = np.clip(np.minimum((freqs - l) / (c - l), (r - freqs) / (r - c)), 0, None)
    return fb, f[1:-1]


def norm01(x, lo=5, hi=99):
    a, b = np.percentile(x, lo), np.percentile(x, hi)
    return np.clip((x - a) / (b - a + 1e-9), 0, 1)


def band_flux(Lm, cf, f0, f1):
    sel = (cf >= f0) & (cf < f1)
    L = Lm[:, sel]
    ref = ndimage.maximum_filter1d(L, 3, axis=1)          # superflux：频率方向先取邻居最大，压掉颤音
    d = np.zeros_like(L)
    d[2:] = L[2:] - ref[:-2]
    return np.maximum(d, 0).sum(1)


def peaks(env, min_gap_s, k=1.0, win_s=1.0):
    """自适应阈值找峰：比周围 win_s 秒的中位数高出 k 倍标准差。返回 (帧号, 强度 0..1)。"""
    w = max(3, int(win_s * FPS) | 1)
    med = ndimage.median_filter(env, w)
    sd = np.sqrt(ndimage.uniform_filter1d((env - med) ** 2, w)) + 1e-9
    idx, _ = signal.find_peaks(env, height=med + k * sd, distance=max(1, int(min_gap_s * FPS)))
    st = env[idx] / (np.percentile(env[idx], 98) + 1e-9) if len(idx) else np.array([])
    return idx, np.clip(st, 0, 1)


def tempo(on, hint=None):
    o = on - on.mean()
    n = len(o)
    F = np.fft.rfft(o, 2 * n)
    ac = np.fft.irfft(F * np.conj(F))[:n]
    ac /= ac[0] + 1e-9
    lags = np.arange(int(FPS * 60 / 200), int(FPS * 60 / 55) + 1)
    sc = np.zeros(len(lags))
    for j, L in enumerate(lags):                           # 梳状打分：节拍那一层在 2、3、4 倍处也有回声
        for k in range(1, 5):
            if k * L < n: sc[j] += ac[k * L] / k
    bpm = 60 * FPS / lags
    center = hint or 115.0
    sc = sc * np.exp(-0.5 * (np.log2(bpm / center) / (0.25 if hint else 0.9)) ** 2)
    j = int(np.argmax(sc))
    if 0 < j < len(sc) - 1:                                 # 抛物线插值到小数帧
        a, b, c = sc[j - 1], sc[j], sc[j + 1]
        dj = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    else:
        dj = 0.0
    return 60 * FPS / (lags[j] + dj)


def beat_dp(on, period, tight=100.0):
    """Ellis 2007 动态规划找拍：拍点落在起音上，相邻两拍的间隔贴近 period。"""
    n = len(on)
    win = np.exp(-0.5 * (np.arange(-int(period), int(period) + 1) * 32.0 / period) ** 2)
    ls = np.convolve(on / (on.std() + 1e-9), win, 'same')
    offs = np.arange(max(1, int(round(period / 2))), int(round(2 * period)) + 1)
    pen = -tight * np.log(offs / period) ** 2
    cum, back = np.zeros(n), np.full(n, -1)
    for t in range(n):
        cand = t - offs
        ok = cand >= 0
        if not ok.any():
            cum[t] = ls[t]; continue
        s = cum[cand[ok]] + pen[ok]
        j = int(np.argmax(s))
        cum[t] = ls[t] + s[j]; back[t] = cand[ok][j]
    lm = signal.argrelmax(cum, order=max(1, int(period / 4)))[0]
    lm = lm[cum[lm] > 0.5 * np.median(cum[lm])] if len(lm) else np.array([n - 1])
    t = int(lm[-1]); bt = []
    while t >= 0:
        bt.append(t); t = back[t]
    bt = np.array(bt[::-1])
    keep = ls[bt] > 0.3 * np.sqrt(np.mean(ls[bt] ** 2))     # 去掉开头结尾安静处的空拍
    return bt[keep], ls


def smooth_grid(bt_s, period_s, full):
    """把逐拍跟踪的拍点理顺成一条连续的网格：漏掉的拍补上、乱跳的扔掉，速度慢慢漂（AI 生成的歌常见）也跟得住。
    返回 (拍点数组, 和原始拍点的偏差 秒, 整体是不是基本恒速)。"""
    k = np.r_[0, np.cumsum(np.round(np.diff(bt_s) / period_s))]   # 跳过的拍按间隔补上编号
    inl = np.ones(len(k), bool)
    for _ in range(6):                                       # 先整体粗拟合，把前奏里乱跳的拍点当离群点扔掉
        A = np.vstack([np.ones(inl.sum()), k[inl]]).T
        (a, b), *_ = np.linalg.lstsq(A, bt_s[inl], rcond=None)
        res = bt_s - (a + b * k)
        inl = np.abs(res) < 0.09
        if inl.sum() < 8: return bt_s, 1.0, False
    kk, tt = k[inl], bt_s[inl]
    ks = np.arange(int(kk.min()), int(kk.max()) + 1)
    est = np.empty(len(ks))
    for j, q in enumerate(ks):                               # 每一拍用前后各约 8 拍做加权直线拟合
        w = np.exp(-0.5 * ((kk - q) / 8.0) ** 2)
        X = np.vstack([np.ones_like(kk), kk - q]).T * np.sqrt(w)[:, None]
        (c0, _), *_ = np.linalg.lstsq(X, tt * np.sqrt(w), rcond=None)
        est[j] = c0
    sd = float(np.std(np.interp(kk, ks, est) - tt))
    per0, per1 = np.median(np.diff(est[:16])), np.median(np.diff(est[-16:]))
    pre = est[0] - per0 * np.arange(int(est[0] / per0), 0, -1)
    post = est[-1] + per1 * np.arange(1, int((full - est[-1]) / per1) + 1)
    beats = np.r_[pre, est, post]
    steady = abs(res[inl]).max() < 0.04
    return beats[(beats >= 0) & (beats <= full)], sd, steady


def chroma_of(S):
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    sel = (freqs >= 65) & (freqs <= 2100)
    pc = (np.round(12 * np.log2(freqs[sel] / 440.0)).astype(int) + 9) % 12
    M = np.zeros((12, sel.sum()), np.float32)
    M[pc, np.arange(sel.sum())] = 1
    C = S[:, sel] @ M.T
    return C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)


def seg_mean(X, edges_f):
    out = []
    for a, b in zip(edges_f[:-1], edges_f[1:]):
        a, b = int(a), max(int(a) + 1, int(b))
        out.append(X[a:b].mean(0))
    return np.array(out)


def parse_lrc(text):
    lines = []
    tag = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\]')
    word = re.compile(r'<(\d+):(\d+(?:\.\d+)?)>')
    for raw in text.splitlines():
        ts = [(int(m.group(1)) * 60 + float(m.group(2))) for m in tag.finditer(raw)]
        body = tag.sub('', raw).strip()
        if not ts or not body: continue
        words = None
        if word.search(body):                                # 增强 LRC：<mm:ss.xx>字
            parts = word.split(body)
            words, clean = [], ''
            i = 1
            while i + 2 <= len(parts):
                t = int(parts[i]) * 60 + float(parts[i + 1]); w = parts[i + 2] if i + 2 < len(parts) else ''
                words.append((t, w)); clean += w; i += 3
            body = clean.strip()
        for t in ts:
            lines.append({'t': t, 'text': body, 'words': words})
    return sorted(lines, key=lambda d: d['t'])


def load_lyrics(path):
    """读歌词：有 [mm:ss.xx] 时间标签就按 LRC 读；没有就当一行一句的纯文本（时间留空，等强制对齐来填）。
    会去掉「作词：」「编曲：」这类署名行。"""
    text = Path(path).read_text(encoding='utf-8-sig')
    credit = re.compile(r'^(编辑|QQ|LRC|www|作词|作曲|编曲|演唱|歌手|制作|混音|母带|和声|吉他|贝斯|鼓|弦乐|监制|出品|发行|专辑|词|曲|OP|SP|Lyrics|Music|Composer|Arranger|Producer)\s*[:：]', re.I)
    if re.search(r'\[\d+:\d+(?:\.\d+)?\]', text):
        ls = [l for l in parse_lrc(text) if not credit.match(l['text'].strip())]
    else:
        ls = [{'t': None, 'text': t.strip(), 'words': None} for t in text.splitlines() if t.strip() and not credit.match(t.strip())]
    return ls


def bars_str(x, n=8):
    blocks = '▁▂▃▄▅▆▇█'
    return blocks[min(n - 1, max(0, int(round(x * (n - 1)))))]


def main():
    ap = argparse.ArgumentParser(description='听歌拆解')
    ap.add_argument('song')
    ap.add_argument('--lrc', '--lyrics', dest='lrc', help='歌词：带时间的 LRC，或者一行一句的纯文本（纯文本要靠强制对齐找时间）'); ap.add_argument('--vocals'); ap.add_argument('--inst')
    ap.add_argument('--stems', help='demucs 分好的文件夹（里面有 drums.wav / vocals.wav / no_vocals.wav 的哪几个都行）')
    ap.add_argument('--start', type=float, default=0.0); ap.add_argument('--end', type=float)
    ap.add_argument('--bpm', type=float); ap.add_argument('--meter', type=int, default=4)
    ap.add_argument('--fade-out', type=float, default=1.2, help='片尾淡出秒数（切在歌中间时用）')
    ap.add_argument('--out', default='.')
    ap.add_argument('--debug', action='store_true')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    y = load(a.song)
    full = len(y) / SR
    start = max(0.0, a.start); end = min(full, a.end or full); dur = end - start
    print(f'整首 {full:.2f} 秒，这次做 {start:.2f}–{end:.2f}（{dur:.2f} 秒）')

    # ---------- 频谱、起音、能量（整首一起分析，速度和段落更稳） ----------
    S = stft_mag(y)
    fb, cf = mel_bank()
    Mel = S @ fb.T
    Lm = np.log1p(100 * Mel / (np.percentile(Mel, 99.5) + 1e-9))
    st = Path(a.stems) if a.stems else None
    pick = lambda name: str(st / name) if st and (st / name).exists() else None
    a.vocals = a.vocals or pick('vocals.wav')
    drum_src = pick('drums.wav') or a.inst or pick('no_vocals.wav')   # 拍点、鼓点优先用鼓轨，其次伴奏
    if drum_src:
        Sd = stft_mag(load(drum_src))
        Sd = np.pad(Sd, ((0, max(0, len(S) - len(Sd))), (0, 0)))[:len(S)]
        Lmd = np.log1p(100 * (Sd @ fb.T) / (np.percentile(Sd @ fb.T, 99.5) + 1e-9))
        print('拍点和鼓点用：', Path(drum_src).name)
    else:
        Lmd = Lm
        print('没给分轨：拍点和鼓点直接从混音里找（有 demucs 的话先分轨，准很多）')
    flux = band_flux(Lmd, cf, 30, 11500)
    kick = band_flux(Lmd, cf, 30, 160)
    snare = band_flux(Lmd, cf, 1200, 5000)
    hat = band_flux(Lmd, cf, 6000, 11500)
    on = ndimage.gaussian_filter1d(flux, 1.0)
    on = np.maximum(on - ndimage.uniform_filter1d(on, int(FPS * 0.5)), 0)   # 去掉慢变的底，只留起音
    pw = (S ** 2).mean(1)
    rms_db = 10 * np.log10(ndimage.uniform_filter1d(pw, 5) + 1e-12)
    low_db = 10 * np.log10(ndimage.uniform_filter1d((Mel[:, cf < 160] ** 2).sum(1), 5) + 1e-12)
    mid_db = 10 * np.log10(ndimage.uniform_filter1d((Mel[:, (cf >= 160) & (cf < 3000)] ** 2).sum(1), 5) + 1e-12)
    high_db = 10 * np.log10(ndimage.uniform_filter1d((Mel[:, cf >= 5000] ** 2).sum(1), 5) + 1e-12)
    nfr = len(S); tl = np.arange(nfr) / FPS

    # ---------- 速度和拍点 ----------
    bpm0 = tempo(on, a.bpm)
    period = FPS * 60 / bpm0
    bt, ls = beat_dp(on, period)
    beats, sd, steady = smooth_grid(bt / FPS, 60 / bpm0, full)
    lf = np.where(rms_db > np.percentile(rms_db, 3) + 6)[0]     # 只去掉开头、结尾的静音；中间的断拍不能删（会把小节数错位）
    beats = beats[(beats >= lf[0] / FPS - 0.05) & (beats <= lf[-1] / FPS + 0.05)]
    per = float(np.median(np.diff(beats)))
    mode = ('速度基本恒定' if steady else '速度有快慢变化') + f'（拍点逐拍跟踪后理顺，和起音偏差 {sd * 1000:.0f} ms）'
    bpm = 60 / per
    print(f'速度 {bpm:.2f} BPM，{mode}，共 {len(beats)} 拍')

    # ---------- 小节头：和声变化 + 底鼓 + 镲 ----------
    C = chroma_of(S)
    bf = np.clip((beats * FPS).astype(int), 0, nfr - 1)
    edges = np.concatenate([bf, [min(nfr, bf[-1] + int(period))]])
    Cb = seg_mean(C, edges)
    Mb = seg_mean(Lm, edges)
    def change(X, w=2):
        d = np.zeros(len(X))
        for i in range(len(X)):
            A = X[max(0, i - w):i]; B = X[i:i + w]
            if len(A) and len(B):
                u, v = A.mean(0), B.mean(0)
                d[i] = 1 - (u @ v) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9)
        return (d - d.mean()) / (d.std() + 1e-9)
    z = lambda x: (x - x.mean()) / (x.std() + 1e-9)
    win = lambda env, i: env[max(0, i - 3):i + 4].max()
    kb = z(np.array([win(kick, i) for i in bf])); cb = z(np.array([win(hat, i) for i in bf])); sb = z(np.array([win(snare, i) for i in bf]))
    m = a.meter
    lines_all = load_lyrics(a.lrc) if a.lrc else []
    if lines_all and any(l['t'] is None for l in lines_all):
        sys.exit('本專案沒有強制對齊：--lrc 每句都要有時間標籤')
    lrc_t = [l['t'] for l in lines_all]
    texts = [re.sub(r'\s+', '', l['text']) for l in lines_all]
    cnt = {t: texts.count(t) for t in texts}
    top = max(cnt.values()) if cnt else 0
    # 每一拍「像小节头」的分：和声 / 音色在这里换、底鼓在这里、军鼓在后一拍（2、4 拍的反拍）、有一句歌词从这里开唱
    nb_ = len(beats)
    back = np.zeros(nb_)
    for i in range(nb_):
        on2 = [sb[j] for j in (i + 1, i + 3) if j < nb_]; on1 = [sb[j] for j in (i, i + 2) if j < nb_]
        back[i] = (np.mean(on2) if on2 else 0) - (np.mean(on1) if on1 else 0)
    ly = np.zeros(nb_)
    for t in lrc_t:
        j = int(np.argmin(np.abs(beats - (t - 0.12))))
        if abs(beats[j] - (t - 0.12)) < 0.24: ly[j] += 1
    Dsc = change(Cb) + 0.6 * change(Mb) + 0.6 * kb + 0.3 * cb + 0.5 * back + 1.2 * ly
    # 动态规划：一般每 m 拍一个小节头；允许偶尔出现 2、3、5、6 拍的小节（歌里常有的加拍、减拍），但要罚分，
    # 只有连着好几小节都说明「换了相位」才会换。之前用一个全曲统一的相位，遇到中间加了两拍的歌就整段错位。
    pen = {m: 0.0, m - 2: 4.0, m - 1: 4.0, m + 1: 4.0, m + 2: 4.0} if m >= 4 else {m: 0.0}
    best = np.full(nb_, -1e9); prev = np.full(nb_, -1)
    for i in range(nb_):
        if i < m: best[i] = Dsc[i]
        for g, pg in pen.items():
            if g > 0 and i - g >= 0 and best[i - g] - pg + Dsc[i] > best[i]:
                best[i] = best[i - g] - pg + Dsc[i]; prev[i] = i - g
    last = max(range(max(0, nb_ - m), nb_), key=lambda i: best[i])
    path = []
    while last >= 0: path.append(last); last = prev[last]
    path = path[::-1]
    downbeats = beats[path]
    odd = [(float(beats[path[k]]), path[k] - path[k - 1]) for k in range(1, len(path)) if path[k] - path[k - 1] != m]
    marg = [Dsc[j] - np.mean([Dsc[x] for x in range(j + 1, min(nb_, j + m))] or [0]) for j in path]
    conf = float(np.mean(marg) / (np.std(Dsc) + 1e-9))
    if a.debug:
        for nm, v in [('和声', change(Cb)), ('音色', change(Mb)), ('底鼓', kb), ('反拍军鼓', back), ('歌词', ly)]:
            print('   ', nm, ' '.join(f'{v[k::m].mean():+.2f}' for k in range(m)))
    print(f'小节头：{len(downbeats)} 个，第一个在 {downbeats[0]:.2f} 秒（把握 {conf:.2f}，<0.3 就自己听一下小节头）'
          + (f'；有 {len(odd)} 处不是 {m} 拍的小节：' + '，'.join(f'{t:.1f}s（{g} 拍）' for t, g in odd[:6]) if odd else ''))

    # ---------- 段落：小节级自相似 + 能量跳变 ----------
    dbf = np.clip((downbeats * FPS).astype(int), 0, nfr - 1)
    bedges = np.concatenate([dbf, [min(nfr, dbf[-1] + int(period * m))]])
    Lr = Lm.reshape(nfr, 24, 3).mean(2)
    feat = np.hstack([z(seg_mean(Lr, bedges)), 1.5 * z(seg_mean(C, bedges))])
    bar_db = np.array([10 * np.log10(pw[int(a_):max(int(a_) + 1, int(b_))].mean() + 1e-12) for a_, b_ in zip(bedges[:-1], bedges[1:])])
    nb = len(feat)
    Fn = feat / (np.linalg.norm(feat, axis=1, keepdims=True) + 1e-9)
    SSM = Fn @ Fn.T
    def foote(K):
        g = np.exp(-0.5 * (np.linspace(-1, 1, 2 * K) / 0.6) ** 2)
        ker = np.outer(g, g) * np.outer(np.r_[-np.ones(K), np.ones(K)], np.r_[-np.ones(K), np.ones(K)])
        P = np.pad(SSM, K, mode='edge')
        v = np.array([(P[i:i + 2 * K, i:i + 2 * K] * ker).sum() for i in range(nb)])
        v = np.maximum(v, 0); return v / (v.max() + 1e-9)
    nov = 0.5 * foote(2) + 0.5 * foote(4)                   # 4 小节和 8 小节两种尺度一起看
    if a.debug:
        n2, n4 = foote(2), foote(4)
        for i in range(nb): print(f'    bar@{downbeats[i]:6.2f}  n2 {n2[i]:.2f}  n4 {n4[i]:.2f}  db {bar_db[i]:.1f}')
    jump = np.r_[0, bar_db[1:] - np.array([bar_db[max(0, i - 2):i].mean() for i in range(1, nb)])]
    cand = {}
    for i in signal.find_peaks(nov, height=0.25, distance=3)[0]: cand[int(i)] = float(nov[i])
    for i in np.where(np.abs(jump) > 3.0)[0]: cand[int(i)] = max(cand.get(int(i), 0), min(1, abs(jump[i]) / 8))
    # 金句：唱得最多的那几句里，带歌名的那句（没有带歌名的就是唱得最多的全部）
    title_key = re.sub(r'[\s（(].*$', '', Path(a.song).stem)
    tops = {t for t in texts if cnt[t] == top}
    hook_set = {t for t in tops if title_key and title_key in t} or tops
    if top >= 3:                                            # 「唱得最多的那几句」连成一串的开头 = 副歌开头
        for j, tx in enumerate(texts):
            if cnt[tx] == top and (j == 0 or cnt[texts[j - 1]] != top):
                tl0 = lines_all[j]['t']                      # 句子常带弱起：取开唱后 1 小节内的第一个小节头
                ok_ = [i for i, dbt in enumerate(downbeats) if tl0 - 0.3 <= dbt <= tl0 + per * m * 1.05]
                if ok_: cand[ok_[0]] = max(cand.get(ok_[0], 0), 0.95)
    cand.pop(0, None)
    bounds = [0]
    for i in sorted(cand, key=lambda i: -cand[i]):
        if cand[i] >= 0.3 and all(abs(i - b) >= 3 for b in bounds) and nb - i >= 2: bounds.append(i)
    bounds = sorted(bounds) + [nb]
    secs = []
    for s0, s1 in zip(bounds[:-1], bounds[1:]):
        secs.append({'b0': s0, 'b1': s1, 'db': float(bar_db[s0:s1].mean()), 'feat': feat[s0:s1].mean(0)})
    letters, protos = [], []
    for s in secs:                                          # 相似的段落用同一个字母（副歌回来还是 B）
        v = s['feat'] / (np.linalg.norm(s['feat']) + 1e-9)
        best = max(range(len(protos)), key=lambda j: protos[j] @ v, default=None)
        if best is not None and protos[best] @ v > 0.75:
            letters.append('ABCDEFGH'[best])
        else:
            protos.append(v); letters.append('ABCDEFGH'[len(protos) - 1])
    db_lo, db_hi = np.percentile(bar_db, 10), np.percentile(bar_db, 95)
    for s, L in zip(secs, letters):
        s['letter'] = L
        s['energy'] = float(np.clip((s['db'] - db_lo) / (db_hi - db_lo + 1e-9), 0, 1))

    # ---------- 歌词 ----------
    vox = None
    if a.vocals:
        yv = load(a.vocals)
        Sv = stft_mag(yv)[:nfr]
        vdb = 10 * np.log10(ndimage.uniform_filter1d((Sv[:, 20:400] ** 2).mean(1), 9) + 1e-12)
        vox = vdb > (np.percentile(vdb, 97) - 30)
        vox = ndimage.binary_closing(vox, np.ones(int(FPS * 0.18)))
        Lv = np.log1p(100 * (Sv @ fb.T) / (np.percentile(Sv @ fb.T, 99.5) + 1e-9))
        vpk, vst = peaks(ndimage.gaussian_filter1d(band_flux(Lv, cf, 150, 6000), 1.0), 0.08, 0.8, 0.6)
        vpk_t = vpk / FPS
    phrases = {}
    for t in set(texts):                                    # 反复出现的短语（≥4 字、出现在 3 句以上）
        for L in range(4, min(10, len(t)) + 1):
            for i in range(len(t) - L + 1):
                p = t[i:i + L]
                c = sum(1 for u in texts if p in u)
                if c >= 3: phrases[p] = max(phrases.get(p, 0), c)
    keep_ph = []
    for p in sorted(phrases, key=lambda p: (-len(p), -phrases[p])):
        if not any(p in q and phrases[q] >= phrases[p] for q in keep_ph): keep_ph.append(p)
    keep_ph = sorted(keep_ph, key=lambda p: -phrases[p])[:6]
    lines = []
    def pick_chars(t0, t1, n):
        """在人声起音里挑 n 个，尽量贴近均分的位置（单调 DP）；起音不够就均分后就近吸附。"""
        even = t0 + (t1 - t0) * np.arange(n) / n
        sel = (vpk_t >= t0 - 0.02) & (vpk_t < t1) & (vst >= 0.12)
        pk = vpk_t[sel]
        if len(pk) < n:
            out = even.copy()
            for j in range(n):
                if len(pk) and np.min(np.abs(pk - even[j])) < 0.08: out[j] = pk[np.argmin(np.abs(pk - even[j]))]
            return list(np.maximum.accumulate(out))
        k = len(pk); INF = 1e9
        D = np.full((n + 1, k + 1), INF); D[0, :] = 0
        for j in range(1, n + 1):
            for q in range(j, k + 1):
                D[j, q] = min(D[j, q - 1], D[j - 1, q - 1] + abs(pk[q - 1] - even[j - 1]))
        out, j, q = [], n, k
        while j > 0:
            if D[j, q] == D[j, q - 1] and q > j: q -= 1
            else: out.append(pk[q - 1]); j -= 1; q -= 1
        return out[::-1]

    seg_win = (start, end) if (a.start > 0 or a.end) else None
    AL, al_note = None, '本專案逐字時間照 docs/production-sop.md，這裡的字時間不採用'
    if lines_all: print('逐字时间：', al_note if AL else f'没有强制对齐（{al_note}），只能估，误差可能大于半秒')
    if AL:                                                   # 强制对齐成功：开唱、唱完、每个字都用它（LRC 只管文字和顺序）
        for l, cs in zip(lines_all, AL):
            if cs is None: continue
            l['t_raw'] = l['t']; ok_ = [c for c in cs if c]
            if ok_:
                l['al'] = [c if c else None for c in cs]; l['t'] = ok_[0][0]
                if abs(l['t'] - l['t_raw']) > 2.0 and (not seg_win or start - 1 <= l['t'] <= end + 1): print(f'  ⚠ 「{l["text"]}」对齐结果和 LRC 差 {l["t"] - l["t_raw"]:+.1f} 秒，用对齐的（LRC 常常不准），但请看一眼')
    for l in lines_all:                                      # 没对齐时：开唱时间吸到最近的人声起音上（LRC 常差 0.1–0.3 秒）
        l.setdefault('t_raw', l['t'])
        if vox is not None and not l['words'] and not l.get('al'):
            near = np.where((np.abs(vpk_t - l['t']) <= 0.25) & (vst >= 0.45))[0]
            if len(near): l['t'] = float(vpk_t[near[np.argmin(np.abs(vpk_t[near] - l['t']))]])
    for i, l in enumerate(lines_all):
        t0 = l['t']; t_next = lines_all[i + 1]['t'] - 0.06 if i + 1 < len(lines_all) else min(full, t0 + 6)
        chars = [c for c in l['text'] if not c.isspace()]
        n = max(1, len(chars))
        if l.get('al'):
            cs = l['al']; last = None; ctimes = []
            for c in cs:                                     # 个别字对不上（零时长）就沿用前一个字的时间
                last = c[0] if c else (last if last is not None else t0); ctimes.append(last)
            ends = [c[1] for c in cs if c]
            sung_end = max(ends) if ends else t0 + 0.3 * n
            src = al_note
        elif l['words']:
            ct, ci = [], 0
            for (wt, w) in l['words']:
                ws = [c for c in w if not c.isspace()]
                ct += [wt] * len(ws)
            sung_end = min(t_next, (l['words'][-1][0] + 0.4))
            ctimes = ct[:n] + [ct[-1]] * (n - len(ct)) if ct else list(np.linspace(t0, sung_end, n, endpoint=False))
            src = '歌词自带逐字时间'
        else:
            if vox is not None:
                f0, f1 = int(t0 * FPS), int(min(t_next, t0 + 8) * FPS)
                v = np.where(vox[f0:f1])[0]
                sung_end = t0 + (v[-1] + 1) / FPS if len(v) else t0 + min(t_next - t0, n * 0.3)
                sung_end = max(sung_end, t0 + 0.12 * n)
                src = '人声起音逐字对齐（开唱吸到人声起音上）'
            else:
                sung_end = t0 + min((t_next - t0) * 0.92, n * 0.5 * per + per)
                src = '按拍子估（没给人声）'
            if vox is not None:
                ctimes = [float(x) for x in pick_chars(t0, sung_end, n)]
            else:
                step = (sung_end - t0) / n
                ctimes = [t0 + k * step for k in range(n)]
        sung_end = min(sung_end, t_next)
        lines.append({'t0': t0, 't1': float(min(t_next, max(sung_end + 0.35, t0 + 0.6))), 'sung_end': float(sung_end),
                      'text': l['text'], 'chars': [{'c': c, 't': float(t)} for c, t in zip(chars, ctimes)],
                      'repeat': cnt[re.sub(r'\s+', '', l['text'])], 'hook': re.sub(r'\s+', '', l['text']) in hook_set and top >= 3,
                      'timing': src})

    # ---------- 事件 ----------
    ki, ks = peaks(ndimage.gaussian_filter1d(kick, 0.8), 0.12, 1.0)
    si, ss = peaks(ndimage.gaussian_filter1d(snare, 0.8), 0.15, 1.2)
    hi_, hs = peaks(ndimage.gaussian_filter1d(hat, 0.8), 0.08, 1.0)
    smooth_db = ndimage.uniform_filter1d(rms_db, int(FPS * 0.06))
    run_db = ndimage.uniform_filter1d(rms_db, int(FPS * 1.5))
    gap = smooth_db < run_db - 9
    stops = []
    lab, nlab = ndimage.label(gap)
    for j in range(1, nlab + 1):
        w = np.where(lab == j)[0]
        if len(w) >= int(FPS * 0.18) and rms_db[w[0]] > np.percentile(rms_db, 10):
            stops.append({'t': w[0] / FPS, 'resume': (w[-1] + 1) / FPS})
    kt = ki / FPS                                           # 底鼓突然停掉一段（EDM 进副歌前常见的「抽鼓」）→ 回来那一下最炸
    for j in range(1, len(kt)):
        gap_ = kt[j] - kt[j - 1]
        if gap_ > 2.6 * per and gap_ < 8 * per * m and j >= 4 and np.median(np.diff(kt[max(0, j - 8):j])) < 1.2 * per:
            stops.append({'t': float(kt[j - 1] + per), 'resume': float(kt[j]), 'kind': '鼓停'})
    drops = []
    for i in range(1, nb):
        if jump[i] > 3.0 and bar_db[i] > np.median(bar_db):
            drops.append({'t': float(downbeats[i]), 'db': float(jump[i])})

    # ---------- 切到这一段（片内秒） ----------
    rel = lambda t: float(round(t - start, 4))
    inside = lambda t, pad=0.0: start - pad <= t <= end + pad
    beats_r = [rel(b) for b in beats if inside(b, per * m)]
    db_r = [rel(d) for d in downbeats if inside(d, per * m)]
    first_db = min([d for d in db_r if d >= -0.05], default=0.0)
    bar_of = lambda t: int(math.floor((t - first_db) / (per * m) + 1e-6)) + 1   # 第 1 小节 = 片内第一个小节头
    db0i = min(range(len(db_r)), key=lambda i: abs(db_r[i] - first_db)) if db_r else 0
    def ref_bar(t):                                         # 按真实的小节头、拍点数（速度有漂移也对得上）
        i = max([k for k, d in enumerate(db_r) if d <= t + 0.03], default=None)
        if i is None: return f'bar{bar_of(t)}'
        bt0 = db_r[i]; b = i - db0i + 1
        nb_ = [x for x in beats_r if bt0 - 0.03 <= x <= t + 0.03]
        return f'bar{b}' if abs(t - bt0) < 0.03 else f'bar{b}.{max(1, len(nb_))}'

    sections = []
    for s in secs:
        t0 = float(downbeats[s['b0']]) if s['b0'] < len(downbeats) else full
        t1 = float(downbeats[s['b1']]) if s['b1'] < len(downbeats) else full
        if t1 <= start or t0 >= end: continue
        sections.append({'t0': rel(max(t0, start)), 't1': rel(min(t1, end)), 'letter': s['letter'], 'energy': round(s['energy'], 3),
                         'bars': s['b1'] - s['b0'], 'cut_in': t0 < start, 'cut_out': t1 > end})
    # 段落名。有歌词：金句开头的 = 副歌，歌词全曲只唱一次的 = 桥段，没人唱 = 间奏，副歌前的短段 = 铺垫，其余 = 主歌。
    # 没歌词：最响、出现两次以上的那组 = 副歌。
    lets = [s['letter'] for s in secs]; en = {L: np.mean([s['energy'] for s in secs if s['letter'] == L]) for L in set(lets)}
    chorus = max(en, key=lambda L: (lets.count(L) >= 2, en[L]))
    for s in sections:
        a0, a1 = s['t0'] + start, s['t1'] + start
        ls_in = [l for l in lines if a0 - 0.5 <= l['t0'] < a1 - 0.5]
        if lines_all:
            top_share = np.mean([l['repeat'] == top for l in ls_in]) if ls_in else 0
            if top >= 3 and (top_share >= 0.5 or any(l['hook'] and l['t0'] < a0 + 1.5 * per * m for l in ls_in)): s['kind'] = '副歌'
            elif not ls_in: s['kind'] = '间奏'
            elif np.mean([l['repeat'] == 1 for l in ls_in]) >= 0.6: s['kind'] = '桥段'
            else: s['kind'] = '主歌'
        else:
            s['kind'] = '副歌' if s['letter'] == chorus else ('安静段' if s['energy'] < 0.35 else '主歌')
    for i, s in enumerate(sections):
        if i + 1 < len(sections) and sections[i + 1]['kind'] == '副歌' and s['kind'] in ('主歌', '间奏') and s['bars'] <= 6 and i > 0:
            s['kind'] = '铺垫'

    ev = lambda idx, st: [{'t': rel(i / FPS), 's': round(float(x), 2)} for i, x in zip(idx, st) if inside(i / FPS)]
    kicks_r, snares_r, hats_r = ev(ki, ks), ev(si, ss), ev(hi_, hs)
    stops_r = [{'t': rel(s['t']), 'resume': rel(s['resume']), 'kind': s.get('kind', '断拍')} for s in stops if inside(s['t'])]
    drops_r = [{'t': rel(d['t']), 'db': round(d['db'], 1)} for d in drops if inside(d['t'])]

    # 大时刻候选：能量跳进、断拍后回来、进副歌、副歌金句第一次出现
    big = []
    for d in drops_r: big.append({'t': d['t'], 'why': f'能量跳高 {d["db"]:.1f} dB（音乐炸开）', 'score': min(1, d['db'] / 6) + 0.3})
    for s in stops_r:
        nxt = [x['t0'] for x in sections if s['resume'] + 0.05 < x['t0'] <= s['resume'] + per * m + 0.05]
        if nxt:   # 鼓先回来一点（加花），下一个小节头才真正进下一段：大时刻放在段落开头
            big.append({'t': s['resume'], 'why': f'{s["t"]:.2f} 秒{s["kind"]}，{s["resume"]:.2f} 秒鼓先加花回来（{nxt[0]:.2f} 秒才真正进下一段）', 'score': 0.6})
            big.append({'t': nxt[0], 'why': f'{s["kind"]}之后整个回来（先停后炸）', 'score': 1.0})
        else:
            big.append({'t': s['resume'], 'why': f'{s["t"]:.2f} 秒{s["kind"]}、{s["resume"]:.2f} 秒回来（先停后炸）', 'score': 1.0 if s['kind'] == '鼓停' else 0.9})
    for s in sections:
        if not s['cut_in'] and s['t0'] > 0.2:
            sc = {'副歌': 0.95, '桥段': 0.75, '铺垫': 0.6, '主歌': 0.6, '间奏': 0.55}.get(s['kind'], 0.5)
            big.append({'t': s['t0'], 'why': f'进{s["kind"]}（段落切换）', 'score': sc})
    seen = set()
    for l in lines:
        k = re.sub(r'\s+', '', l['text'])
        if l['hook'] and inside(l['t0']) and k not in seen:
            seen.add(k); big.append({'t': rel(l['t0']), 'why': f'金句「{l["text"]}」第一次唱', 'score': 0.7})
    big.sort(key=lambda b: b['t'])
    merged = []
    for b in big:                                           # 一拍以内的合成一个
        if merged and abs(b['t'] - merged[-1]['t']) < per * 1.01:
            merged[-1]['why'] += '；' + b['why']; merged[-1]['score'] = max(merged[-1]['score'], b['score'])
            if b['score'] > 0.85: merged[-1]['t'] = b['t']
        else: merged.append(dict(b))
    for b in merged:
        b['at'] = ref_bar(b['t']); b['score'] = round(min(1.0, b['score']), 2)

    # ---------- 60 帧曲线 ----------
    tt = np.arange(0, dur + 1e-9, 1 / OUT_FPS) + start
    curve = lambda x: [round(float(v), 3) for v in np.interp(tt, tl, x)]
    env = {'fps': OUT_FPS, 'energy': curve(ndimage.uniform_filter1d(norm01(rms_db), 6)),
           'low': curve(norm01(low_db)), 'mid': curve(norm01(mid_db)), 'high': curve(norm01(high_db)),
           'onset': curve(norm01(on, 50, 99.5))}

    lines_r = []
    for l in lines:
        if l['t0'] >= end - 0.2: continue
        if l['t0'] < start - 0.3 and (l['sung_end'] - start) < 0.5 * (l['sung_end'] - l['t0']): continue     # 大半在段外的句子不算
        lines_r.append({'n': len(lines_r) + 1, 't0': rel(l['t0']), 't1': rel(min(l['t1'], end)), 'sung_end': rel(l['sung_end']),
                        'text': l['text'], 'repeat': l['repeat'], 'hook': l['hook'], 'timing': l['timing'], 'at': ref_bar(rel(l['t0'])),
                        'chars': [{'c': c['c'], 't': rel(c['t'])} for c in l['chars']]})

    song = {'title': Path(a.song).stem, 'source': str(Path(a.song).resolve()), 'start': start, 'end': end, 'dur': round(dur, 4),
            'bpm': round(bpm, 3), 'beat': round(per, 5), 'meter': m, 'bar': round(per * m, 5), 'first_downbeat': first_db,
            'beat_mode': mode, 'downbeat_confidence': round(float(conf), 2),
            'beats': beats_r, 'downbeats': db_r, 'sections': sections, 'lines': lines_r, 'phrases': [{'text': p, 'lines': phrases[p]} for p in keep_ph],
            'kicks': kicks_r, 'snares': snares_r, 'hats': hats_r, 'stops': stops_r, 'drops': drops_r, 'big': merged, 'env': env}
    (out / 'song.json').write_text(json.dumps(song, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    # ---------- 切音频 ----------
    fo = min(a.fade_out, dur / 4) if end < full - 0.05 else 0
    af = f'atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015'
    if fo > 0: af += f',afade=t=out:st={dur - fo:.4f}:d={fo:.3f}'
    subprocess.run([FF, '-y', '-v', 'error', '-i', str(a.song), '-af', af, '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(out / 'audio.wav')], check=True)

    write_md(out / 'song.md', song, env)
    try:
        draw_map(out / 'songmap.png', song, env)
    except Exception as e:
        print('songmap.png 没画出来（不影响后面）：', e)
    print(f'写好了 {out / "song.json"}、song.md、songmap.png、audio.wav')
    print(f'{len(lines_r)} 句歌词，{len(sections)} 个段落，{len(merged)} 个大时刻候选，{len(kicks_r)} 个底鼓')


def write_md(path, s, env):
    E = env['energy']; fps = env['fps']
    DB = s['downbeats']; i1 = min(range(len(DB)), key=lambda i: abs(DB[i] - s['first_downbeat'])) if DB else 0
    def barno(t):                                           # 按真实小节头编号（不按平均速度推）
        k = max([i for i, d in enumerate(DB) if d <= t + 0.03], default=None)
        return 0 if k is None else k - i1 + 1
    at = lambda t: E[min(len(E) - 1, max(0, int(t * fps)))]
    L = [f'# 歌曲拆解：{s["title"]}（整首 {s["start"]:.2f}–{s["end"]:.2f} 秒，片长 {s["dur"]:.2f} 秒）', '',
         f'- 速度 **{s["bpm"]:.2f} BPM**，一拍 {s["beat"]:.3f} 秒，一小节（{s["meter"]} 拍）{s["bar"]:.3f} 秒；{s["beat_mode"]}',
         f'- 片内第一个小节头在 **{s["first_downbeat"]:.3f} 秒** = `bar1`（之前那一点是弱起，算 bar0）。小节头把握 {s["downbeat_confidence"]}',
         '- 卡点表里写时间：`bar9` = 第 9 小节第一拍，`bar9.3` = 第 9 小节第 3 拍，`line4` = 第 4 句开唱，后面可以加 `+0.5b`（拍）或 `-0.1s`（秒）',
         '- 秒数以 song.json 为准（小节头逐个测的，速度有快慢也对得上）；这张表的秒数只给人看，代码里一律写 bar / line，别抄秒数。逐小节表里写着（2 拍）（5 拍）的是不规则小节。', '']
    L += ['## 段落', '', '| 段 | 片内秒 | 小节 | 能量 | 像什么 | 这段唱的 |', '|---|---|---|---|---|---|']
    for i, x in enumerate(s['sections']):
        ly = ' / '.join(l['text'] for l in s['lines'] if x['t0'] - 0.3 <= l['t0'] < x['t1'] - 0.3)
        b0 = barno(x['t0']); b1 = barno(x['t1'] - 0.05) + 1
        cut = ('（从中间切进来）' if x['cut_in'] else '') + ('（切在中间）' if x['cut_out'] else '')
        L.append(f'| {x["letter"]}{i + 1} | {x["t0"]:.2f}–{x["t1"]:.2f} | bar{b0}–bar{b1} | {x["energy"]:.2f} {"█" * int(round(x["energy"] * 10))} | {x["kind"]}{cut} | {ly} |')
    L += ['', '同一个字母 = 音乐上是同一种段落（副歌回来还是同一个字母）。', '',
          '## 大时刻候选（音乐上最该「炸」的点，卡点表里至少挑 3 个做成大时刻）', '']
    for b in s['big']:
        L.append(f'- **{b["t"]:.2f} 秒 `{b["at"]}`**：{b["why"]}（分 {b["score"]}）')
    if s['stops']:
        L += ['', '断拍 / 抽鼓（音乐突然停一下，回来那一下最该炸）：' + '，'.join(f'{x["kind"]} {x["t"]:.2f}→{x["resume"]:.2f}' for x in s['stops'])]
    L += ['', '## 歌词（`hook` = 全曲出现最多的金句；逐字时间在 song.json）', '', '| 句 | 开唱 | 唱完 | 位置 | 歌词 | 出现 |', '|---|---|---|---|---|---|']
    for l in s['lines']:
        L.append(f'| line{l["n"]} | {l["t0"]:.2f} | {l["sung_end"]:.2f} | `{l["at"]}` | {l["text"]}{" **(hook)**" if l["hook"] else ""} | {l["repeat"]} 次 |')
    if s['phrases']:
        L += ['', '反复出现的短语：' + '，'.join(f'「{p["text"]}」{p["lines"]} 句' for p in s['phrases'])]
    if s['lines']:
        L += ['', f'逐字时间来源：{s["lines"][0]["timing"]}']
    L += ['', '## 逐小节', '', '| 小节 | 片内秒 | 段 | 能量 | 底鼓 | 军鼓 | 这一小节开唱的歌词 | 事件 |', '|---|---|---|---|---|---|---|---|']
    rows = ([(0, 0.0, s['first_downbeat'])] if s['first_downbeat'] > 0.05 else [])
    for k in range(i1, len(DB)):
        if DB[k] >= s['dur']: break
        rows.append((k - i1 + 1, DB[k], DB[k + 1] if k + 1 < len(DB) else s['dur']))
    for b, t0, t1 in rows:
        nbeat = sum(1 for x in s['beats'] if t0 - 0.03 <= x < t1 - 0.03)
        if t0 >= s['dur']: break
        sec = next((f'{x["letter"]}{i + 1}' for i, x in enumerate(s['sections']) if x['t0'] - 0.05 <= t0 < x['t1']), '')
        es = ''.join(bars_str(at(x)) for x in s['beats'] if t0 - 0.03 <= x < t1 - 0.03 and x < s['dur'])
        nk = sum(1 for k in s['kicks'] if t0 - 0.03 <= k['t'] < t1 - 0.03); ns = sum(1 for k in s['snares'] if t0 - 0.03 <= k['t'] < t1 - 0.03)
        ly = ' / '.join(f'line{l["n"]}「{l["text"]}」' for l in s['lines'] if t0 - 0.03 <= l['t0'] < t1 - 0.03)
        evs = [b_['why'].split('（')[0] for b_ in s['big'] if t0 - 0.03 <= b_['t'] < t1 - 0.03]
        evs += [x['kind'] + '开始' for x in s['stops'] if t0 <= x['t'] < t1]
        odd = f'（{nbeat} 拍）' if b >= 1 and nbeat != s['meter'] else ''
        L.append(f'| bar{b}{odd} | {t0:.2f} | {sec} | {es} | {nk} | {ns} | {ly} | {"；".join(evs)} |')
    path.write_text('\n'.join(L) + '\n', encoding='utf-8')


def draw_map(path, s, env):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC', 'PingFang SC', 'Source Han Sans SC']:
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams['font.family'] = name; break
    plt.rcParams['axes.unicode_minus'] = False
    dur = s['dur']; fps = env['fps']
    t = np.arange(len(env['energy'])) / fps
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(max(16, dur * 0.42), 7.2), dpi=110, gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    fig.patch.set_facecolor('#16161a')
    cols = {'A': '#3b6ea5', 'B': '#c0504d', 'C': '#4f9a6b', 'D': '#a0782a', 'E': '#7d5ba6', 'F': '#2f8f8f', 'G': '#8a8a8a', 'H': '#b05f8f'}
    for a_ in (ax, ax2):
        a_.set_facecolor('#1d1d22'); a_.tick_params(colors='#bbb'); [sp.set_color('#444') for sp in a_.spines.values()]
    for i, x in enumerate(s['sections']):
        ax.axvspan(x['t0'], x['t1'], color=cols.get(x['letter'], '#888'), alpha=0.22, lw=0)
        ax.text(x['t0'] + 0.1, 1.17, f'{x["letter"]}{i + 1} {x["kind"]}', color=cols.get(x['letter'], '#ccc'), fontsize=11, weight='bold', va='top')
    ax.fill_between(t, 0, env['energy'], color='#e8c170', alpha=0.55, lw=0, label='能量')
    ax.plot(t, env['low'], color='#ff7a59', lw=0.8, alpha=0.8, label='低频')
    ax.plot(t, env['high'], color='#7fd3ff', lw=0.6, alpha=0.6, label='高频')
    for b in s['beats']:
        if 0 <= b <= dur: ax.axvline(b, color='#666', lw=0.5, alpha=0.6)
    for i, d in enumerate(s['downbeats']):
        if -0.05 <= d <= dur:
            ax.axvline(d, color='#ddd', lw=1.0, alpha=0.8)
            ax.text(d + 0.04, -0.05, f'bar{round((d - s["first_downbeat"]) / s["bar"]) + 1}', color='#ccc', fontsize=7, va='top')
    for k, l in enumerate(s['lines']):
        y = 0.98 - (k % 3) * 0.1
        ax.annotate(f'line{l["n"]} {l["text"]}', (max(0, l['t0']), y), color='#fff' if not l['hook'] else '#ffd34d', fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.2', fc='#000', ec='#ffd34d' if l['hook'] else '#555', alpha=0.7))
        ax.plot([max(0, l['t0']), l['sung_end']], [y - 0.035, y - 0.035], color='#ffd34d' if l['hook'] else '#aaa', lw=2)
    for b in s['big']:
        ax.plot([b['t']], [1.05], marker='v', color='#ff3b3b', ms=6 + 8 * b['score'])
    ax.set_ylim(-0.1, 1.2); ax.set_xlim(0, dur)
    ax.legend(loc='lower right', fontsize=8, facecolor='#222', labelcolor='#ddd', edgecolor='#444')
    for name, c, yy in [('kicks', '#ff7a59', 0.75), ('snares', '#7fd36b', 0.45), ('hats', '#7fd3ff', 0.15)]:
        xs = [e['t'] for e in s[name]]; ss = [e['s'] for e in s[name]]
        ax2.scatter(xs, [yy] * len(xs), s=[6 + 40 * v for v in ss], color=c, label={'kicks': '底鼓', 'snares': '军鼓', 'hats': '镲'}[name])
    ax2.plot(t, np.array(env['onset']) * 0.25 + 0.0, color='#ccc', lw=0.5)
    ax2.set_ylim(0, 1); ax2.set_yticks([]); ax2.set_xlabel('片内秒', color='#bbb')
    ax2.legend(loc='upper right', fontsize=8, facecolor='#222', labelcolor='#ddd', edgecolor='#444', ncol=3)
    ax.set_title(f'{s["title"]} · {s["bpm"]:.1f} BPM · {s["start"]:.1f}–{s["end"]:.1f} 秒（红三角 = 大时刻候选，金色 = hook 金句）', color='#eee', fontsize=12, loc='left')
    fig.tight_layout(); fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)


if __name__ == '__main__':
    main()
