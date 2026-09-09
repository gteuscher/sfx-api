"""Port of the sfxr synthesis loop (DrPetter, 2007; public domain via jsfxr).

Parameter names and value ranges match jsfxr so existing presets paste in.
Renders at 44100 Hz like the original; the caller resamples if needed.
"""

from __future__ import annotations

import math

import numpy as np

from sfx.spec.models import SfxrSource

SFXR_RATE = 44100
_WAVES = {"square": 0, "saw": 1, "sine": 2, "noise": 3}


def sfxr_length_samples(p: SfxrSource) -> int:
    return int((p.p_env_attack**2 + p.p_env_sustain**2 + p.p_env_decay**2) * 100000)


def render_sfxr(p: SfxrSource, rng: np.random.Generator, supersample: int = 8) -> np.ndarray:
    wave = _WAVES[p.wave]
    total = sfxr_length_samples(p)
    out = np.zeros(total, dtype=np.float64)
    env_length = [p.p_env_attack**2 * 100000, p.p_env_sustain**2 * 100000, p.p_env_decay**2 * 100000]

    # state shared between partial resets
    st: dict = {}

    def reset(full: bool) -> None:
        st["fperiod"] = 100.0 / (p.p_base_freq**2 + 0.001)
        st["period"] = int(st["fperiod"])
        st["fmaxperiod"] = 100.0 / (p.p_freq_limit**2 + 0.001)
        st["fslide"] = 1.0 - p.p_freq_ramp**3 * 0.01
        st["fdslide"] = -(p.p_freq_dramp**3) * 0.000001
        st["square_duty"] = 0.5 - p.p_duty * 0.5
        st["square_slide"] = -p.p_duty_ramp * 0.00005
        st["arp_mod"] = 1.0 - p.p_arp_mod**2 * 0.9 if p.p_arp_mod >= 0 else 1.0 + p.p_arp_mod**2 * 10.0
        st["arp_time"] = 0
        st["arp_limit"] = 0 if p.p_arp_speed == 1.0 else int((1.0 - p.p_arp_speed) ** 2 * 20000 + 32)
        if full:
            st["phase"] = 0
            st["fltp"] = 0.0
            st["fltdp"] = 0.0
            st["fltw"] = p.p_lpf_freq**3 * 0.1
            st["fltw_d"] = 1.0 + p.p_lpf_ramp * 0.0001
            st["fltdmp"] = min(5.0 / (1.0 + p.p_lpf_resonance**2 * 20) * (0.01 + st["fltw"]), 0.8)
            st["fltphp"] = 0.0
            st["flthp"] = p.p_hpf_freq**2 * 0.1
            st["flthp_d"] = 1.0 + p.p_hpf_ramp * 0.0003
            st["vib_phase"] = 0.0
            st["vib_speed"] = p.p_vib_speed**2 * 0.01
            st["vib_amp"] = p.p_vib_strength * 0.5
            st["env_vol"] = 0.0
            st["env_stage"] = 0
            st["env_time"] = 0
            st["fphase"] = math.copysign(p.p_pha_offset**2 * 1020, p.p_pha_offset)
            st["fdphase"] = math.copysign(p.p_pha_ramp**2, p.p_pha_ramp)
            st["iphase"] = abs(int(st["fphase"]))
            st["ipp"] = 0
            st["pha_buf"] = [0.0] * 1024
            st["noise_buf"] = list(rng.uniform(-1, 1, 32))
            st["rep_time"] = 0
            st["rep_limit"] = 0 if p.p_repeat_speed == 0 else int((1.0 - p.p_repeat_speed) ** 2 * 20000 + 32)

    reset(True)
    s = st  # local alias for speed
    pha_buf = s["pha_buf"]
    noise_buf = s["noise_buf"]
    sin = math.sin
    two_pi = 2 * math.pi
    lpf_bypass = p.p_lpf_freq == 1.0

    for i in range(total):
        s["rep_time"] += 1
        if s["rep_limit"] != 0 and s["rep_time"] >= s["rep_limit"]:
            s["rep_time"] = 0
            reset(False)
        s["arp_time"] += 1
        if s["arp_limit"] != 0 and s["arp_time"] >= s["arp_limit"]:
            s["arp_limit"] = 0
            s["fperiod"] *= s["arp_mod"]
        s["fslide"] += s["fdslide"]
        s["fperiod"] *= s["fslide"]
        if s["fperiod"] > s["fmaxperiod"]:
            s["fperiod"] = s["fmaxperiod"]
            if p.p_freq_limit > 0:
                break
        rfperiod = s["fperiod"]
        if s["vib_amp"] > 0:
            s["vib_phase"] += s["vib_speed"]
            rfperiod = s["fperiod"] * (1.0 + sin(s["vib_phase"]) * s["vib_amp"])
        period = max(int(rfperiod), 8)
        s["square_duty"] = min(max(s["square_duty"] + s["square_slide"], 0.0), 0.5)
        square_duty = s["square_duty"]

        s["env_time"] += 1
        if s["env_time"] > env_length[s["env_stage"]]:
            s["env_time"] = 0
            s["env_stage"] += 1
            if s["env_stage"] == 3:
                break
        stage = s["env_stage"]
        et = s["env_time"]
        if stage == 0:
            env_vol = et / env_length[0] if env_length[0] else 1.0
        elif stage == 1:
            env_vol = 1.0 + (1.0 - (et / env_length[1] if env_length[1] else 1.0)) * 2.0 * p.p_env_punch
        else:
            env_vol = 1.0 - (et / env_length[2] if env_length[2] else 1.0)

        s["fphase"] += s["fdphase"]
        iphase = min(abs(int(s["fphase"])), 1023)
        if s["flthp_d"] != 0:
            s["flthp"] = min(max(s["flthp"] * s["flthp_d"], 0.00001), 0.1)
        flthp = s["flthp"]

        ssample = 0.0
        phase = s["phase"]
        fltp, fltdp, fltphp, fltw, ipp = s["fltp"], s["fltdp"], s["fltphp"], s["fltw"], s["ipp"]
        for _ in range(supersample):
            phase += 1
            if phase >= period:
                phase %= period
                if wave == 3:
                    noise_buf[:] = rng.uniform(-1, 1, 32)
            fp = phase / period
            if wave == 0:
                sample = 0.5 if fp < square_duty else -0.5
            elif wave == 1:
                sample = 1.0 - fp * 2
            elif wave == 2:
                sample = sin(fp * two_pi)
            else:
                sample = noise_buf[phase * 32 // period]
            pp = fltp
            fltw = min(max(fltw * s["fltw_d"], 0.0), 0.1)
            if not lpf_bypass:
                fltdp += (sample - fltp) * fltw
                fltdp -= fltdp * s["fltdmp"]
            else:
                fltp = sample
                fltdp = 0.0
            fltp += fltdp
            fltphp += fltp - pp
            fltphp -= fltphp * flthp
            sample = fltphp
            pha_buf[ipp & 1023] = sample
            sample += pha_buf[(ipp - iphase + 1024) & 1023]
            ipp = (ipp + 1) & 1023
            ssample += sample * env_vol
        s["phase"], s["fltp"], s["fltdp"], s["fltphp"], s["fltw"], s["ipp"] = phase, fltp, fltdp, fltphp, fltw, ipp
        ssample = ssample / supersample * 0.05 * 2.0 * p.sound_vol
        out[i] = min(max(ssample, -1.0), 1.0)
    return out[: i + 1] if total else out


def render_sfxr_at(p: SfxrSource, sr: int, rng: np.random.Generator) -> np.ndarray:
    x = render_sfxr(p, rng)
    if sr == SFXR_RATE or len(x) == 0:
        return x
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr, SFXR_RATE)
    return resample_poly(x, sr // g, SFXR_RATE // g)
