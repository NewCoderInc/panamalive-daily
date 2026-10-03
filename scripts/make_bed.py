#!/usr/bin/env python3
"""
Compose the reel's background bed: an original jazzy hip-hop / R&B loop.

    python3 make_bed.py --seconds 12 --out bed.wav

Written rather than sourced on purpose. A commercial track on a business
account is a copyright strike waiting to happen, and Instagram's own licensed
library is only available at upload time, not to a file built here. This is
generated from scratch, so the account owns what it posts -- and if a licensed
track is preferred, Instagram can layer one over it at upload.

The musical content: 82 BPM, a two-bar boom-bap pattern under a ii-V-I-VI
turnaround in F (Gm9 - C13 - Fmaj9 - Dm9) voiced as Rhodes-ish FM tines, with
an upright-style bass on roots and fifths. Everything is synthesised with
numpy: sine stacks for the tines, a filtered sine drop for the kick, shaped
noise for snare and hats.
"""
import argparse, math, wave
import numpy as np

SR = 44100
BPM = 82.0
BEAT = 60.0 / BPM

# ii - V - I - VI in F, one bar each. Semitone offsets from A4 = 440 Hz.
CHORDS = [
    [-2, 5, 10, 14],    # Gm9   : G Bb D F(9)
    [3, 10, 14, 19],    # C13   : C E G A
    [-4, 0, 7, 11],     # Fmaj9 : F A C E
    [-7, 0, 5, 9],      # Dm9   : D F A C
]
ROOTS = [-14, -9, -16, -19]


def hz(semis):
    return 440.0 * (2.0 ** (semis / 12.0))


def env(n, attack, decay, sustain=0.0, release=0.25):
    """A simple ADSR over n samples, expressed in seconds for the stages."""
    a, d, r = int(attack * SR), int(decay * SR), int(release * SR)
    a, d = max(a, 1), max(d, 1)
    body = max(n - a - d - r, 0)
    e = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, sustain, d),
        np.full(body, sustain),
        np.linspace(sustain, 0, max(r, 1)),
    ])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def tine(f, dur, amp=0.25):
    """An FM 'electric piano' voice: a carrier plus a bell-like modulator whose
    index decays, which is what makes a Rhodes read as a Rhodes and not an
    organ."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * math.pi * f * 2.0 * t) * np.exp(-t * 6.0) * 2.4
    y = np.sin(2 * math.pi * f * t + mod)
    y += 0.25 * np.sin(2 * math.pi * f * 2 * t) * np.exp(-t * 3.0)
    return y * env(n, 0.004, 0.5, 0.35, dur * 0.5) * amp


def bass(f, dur, amp=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * math.pi * f * t) + 0.3 * np.sin(2 * math.pi * f * 2 * t)
    y += 0.12 * np.sin(2 * math.pi * f * 3 * t) * np.exp(-t * 9.0)   # pluck
    return y * env(n, 0.006, 0.28, 0.55, 0.12) * amp


def kick(amp=0.9):
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    f = 105 * np.exp(-t * 26) + 44          # pitch drop = the thump
    y = np.sin(2 * math.pi * np.cumsum(f) / SR)
    return y * np.exp(-t * 11) * amp


def snare(amp=0.5):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(7).normal(0, 1, n)
    # one-pole high-pass so it cracks instead of thuds
    hp = np.diff(np.concatenate([[0.0], noise]))
    tone = np.sin(2 * math.pi * 185 * t) * 0.6
    return (hp * 0.8 + tone) * np.exp(-t * 19) * amp


def hat(open_=False, amp=0.22):
    n = int((0.16 if open_ else 0.055) * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(11).normal(0, 1, n)
    hp = np.diff(np.concatenate([[0.0], noise]))
    return hp * np.exp(-t * (10 if open_ else 42)) * amp


def add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[:j - i]


def build(seconds):
    total = int(seconds * SR) + SR
    left = np.zeros(total)
    right = np.zeros(total)
    bar = BEAT * 4
    bars = int(math.ceil(seconds / bar)) + 1

    for b in range(bars):
        t0 = b * bar
        ch = CHORDS[b % len(CHORDS)]
        root = ROOTS[b % len(ROOTS)]

        # Chord on the 1 and a pushed stab on the "and of 2" -- the push is
        # what stops a loop like this sounding like a hold-music pad.
        for start, dur, amp in ((0.0, bar * 0.62, 0.22), (BEAT * 1.5, BEAT * 1.4, 0.15)):
            for k, semi in enumerate(ch):
                v = tine(hz(semi), dur, amp)
                pan = 0.5 + (k - 1.5) * 0.10        # spread the voicing
                add(left, v * (1 - pan), t0 + start)
                add(right, v * pan, t0 + start)

        # Bass: root on 1, fifth on the "and of 3"
        for start, semi, dur in ((0.0, root, BEAT * 1.6),
                                 (BEAT * 2.5, root + 7, BEAT * 1.1)):
            v = bass(hz(semi), dur)
            add(left, v * 0.5, t0 + start)
            add(right, v * 0.5, t0 + start)

        # Boom-bap: kick 1 and the "and of 2"+3, snare on 2 and 4
        for at in (0.0, BEAT * 1.75, BEAT * 2.5):
            k = kick()
            add(left, k * 0.5, t0 + at)
            add(right, k * 0.5, t0 + at)
        for at in (BEAT, BEAT * 3):
            s = snare()
            add(left, s * 0.5, t0 + at)
            add(right, s * 0.5, t0 + at)
        for i in range(8):                            # swung eighths
            at = i * BEAT / 2 + (0.055 if i % 2 else 0.0)
            h = hat(open_=(i == 7))
            add(left, h * 0.42, t0 + at)
            add(right, h * 0.58, t0 + at)

    n = int(seconds * SR)
    left, right = left[:n], right[:n]
    st = np.stack([left, right], axis=1)
    st /= max(np.abs(st).max(), 1e-9)
    st *= 0.82
    # 0.4s fade in, 1.2s fade out, so the loop never clicks on or off
    fi, fo = int(0.4 * SR), int(1.2 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--out", default="bed.wav")
    a = ap.parse_args()
    st = build(a.seconds)
    pcm = (st * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote %s (%.1fs, %.0f BPM)" % (a.out, a.seconds, BPM))


if __name__ == "__main__":
    main()
