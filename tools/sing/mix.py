"""人聲（歌聲合成匯出）＋伴奏（render.py 算的 wav）混音。只用 numpy（專案規則：不依賴 scipy）。

人聲：高通 100Hz（FFT）→ 輕壓縮（-20dB、2.5:1）→ 殘響（合成脈衝響應，FFT 卷積）
平衡：只比「人聲有聲音」的片段，人聲 RMS 比伴奏高 vocal_db
母帶：軟限幅、峰值 -1 dBFS，輸出 44.1kHz 16-bit 立體聲 wav
兩個檔案都從 0 秒開始、取樣率要相同（OpenUtau 匯出與 FluidSynth 預設都是 44.1kHz）；人聲 MIDI 與伴奏用同一個 --intro-bars 就會對齊。

--warm：人聲「磁性」處理（中低頻加厚、收刺耳與齒音、輕微飽和），在高通之後、壓縮之前
用法：python mix.py <人聲 wav> <伴奏 wav> <輸出 wav> [--vocal-db 2] [--reverb 0.18] [--warm 1]
"""
import argparse

import numpy as np

from song import read_wav, write_wav


def read(path):
    return read_wav(path, stereo=True)


def highpass(x, sr, fc):
    spec = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    spec *= (1 / np.sqrt(1 + (fc / np.maximum(f, 1e-6)) ** 4))[:, None]  # 二階斜率
    return np.fft.irfft(spec, n=len(x), axis=0)


def compress(x, sr, thresh_db=-20, ratio=2.5, win=0.03):
    mono = np.abs(x).mean(1)
    k = int(sr * win)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(k) / k, mode="same")) + 1e-9
    lvl = 20 * np.log10(env)
    gain_db = np.where(lvl > thresh_db, (thresh_db - lvl) * (1 - 1 / ratio), 0)
    k2 = int(sr * 0.05)
    gain_db = np.convolve(gain_db, np.ones(k2) / k2, mode="same")  # 平滑避免抽動
    return x * (10 ** (gain_db / 20))[:, None]


def reverb(x, sr, wet, seconds=1.6, seed=0):
    rng = np.random.default_rng(seed)
    n = int(sr * seconds)
    t = np.arange(n) / sr
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 6.9 / seconds)[:, None]  # RT60 ≈ seconds
    ir[: int(sr * 0.02)] = 0  # 20ms 預延遲
    ir = highpass(ir, sr, 300)
    ir /= np.sqrt((ir ** 2).sum(0))
    L = len(x) + n
    nfft = 1 << (L - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft, axis=0) * np.fft.rfft(ir, nfft, axis=0), nfft, axis=0)[: len(x)]
    return x * (1 - wet) + y * wet * 2.0


def warm(x, sr, amount=1.0):
    """「磁性」處理：中低頻（約 250Hz）加厚、2～4kHz 刺耳處與 7kHz 齒音略收，再輕微飽和。amount 0～1.5"""
    spec = np.fft.rfft(x, axis=0)
    f = np.maximum(np.fft.rfftfreq(len(x), 1 / sr), 1)

    def bell(fc, db, octaves):
        return db * np.exp(-0.5 * (np.log2(f / fc) / (octaves / 2)) ** 2)

    g = amount * (bell(250, 3.5, 1.6) + bell(3000, -2.0, 1.5) + bell(7000, -3.0, 1.0))
    y = np.fft.irfft(spec * (10 ** (g / 20))[:, None], n=len(x), axis=0)
    drive = 1 + 1.5 * amount
    peak = np.abs(y).max() + 1e-9
    return np.tanh(y / peak * drive) / np.tanh(drive) * peak


def rms(x):
    return np.sqrt((x ** 2).mean()) + 1e-12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vocal")
    ap.add_argument("acc")
    ap.add_argument("out")
    ap.add_argument("--vocal-db", type=float, default=2.0, help="歌唱段落人聲比伴奏大幾 dB")
    ap.add_argument("--reverb", type=float, default=0.18)
    ap.add_argument("--warm", type=float, default=0, help="人聲「磁性」處理強度 0～1.5（0＝不處理）")
    a = ap.parse_args()
    v, sr = read(a.vocal)
    acc, sr2 = read(a.acc)
    assert sr == sr2, (sr, sr2)
    n = max(len(v), len(acc))
    v = np.pad(v, ((0, n - len(v)), (0, 0)))
    acc = np.pad(acc, ((0, n - len(acc)), (0, 0)))

    v = highpass(v, sr, 100)
    if a.warm:
        v = warm(v, sr, a.warm)
    v = compress(v, sr)
    v = reverb(v, sr, a.reverb)

    # 只用「人聲有聲音」的片段比較音量
    hop = int(sr * 0.05)
    frames = np.array([rms(v[i:i + hop]) for i in range(0, n - hop, hop)])
    sung = np.repeat(frames > frames.max() * 0.1, hop)[:n]
    sung = np.pad(sung, (0, n - len(sung)))
    g = 10 ** (a.vocal_db / 20) * rms(acc[sung]) / rms(v[sung])
    mix = acc + v * g

    peak = np.abs(mix).max()
    mix = mix / peak * 1.12  # 略推進軟限幅區
    mix = np.tanh(mix) / np.tanh(1.12) * 10 ** (-1 / 20)  # 峰值 -1 dBFS
    write_wav(a.out, mix, sr)
    print(f"人聲增益 {20 * np.log10(g):+.1f} dB；長度 {n / sr:.1f} 秒；整體 RMS {20 * np.log10(rms(mix)):.1f} dBFS")


if __name__ == "__main__":
    main()
