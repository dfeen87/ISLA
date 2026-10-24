"""Deterministic offline state analysis and three explicitly different operations.

This is an operational acoustic-regime model, not polyphonic note separation.
All spectra are channels x bins; shared gains/phase changes never mix channels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import numpy as np

REGIMES = ("attack", "bloom", "sustain", "decay", "overlap", "silence")
MODES = ("velvet", "legato", "melt")
VARIANTS = ("governed", "fixed", "fixed_matched", "attack_gated", "shuffled", "noop")


@dataclass(frozen=True)
class Config:
    frame: int = 2048
    hop: int = 512
    floor: float = 1e-10
    silence_rms: float = 1e-5  # -100 dBFS; no generated tail below this threshold
    reliability_ratio: float = 1e-3  # amplitude -60 dB from frame maximum
    onset_flux: float = .35  # 35% positive spectral replacement per hop
    bloom_s: float = .12
    resonance_s: float = .18
    legato_memory_s: float = .08
    melt_frequency_s: float = .06
    recovery_s: float = .10  # zero-to-full control slew time
    velvet_depth: float = .16
    legato_depth: float = .30
    melt_depth: float = .30
    gain_min: float = .80
    gain_max: float = 1.188502227  # +1.5 dB common per-bin amplitude ceiling
    phase_max_rad: float = .10
    seed: int = 20261024


def principal(x):
    """Principal angle in [-pi, pi); endpoint choice has no acoustic effect."""
    return (x + np.pi) % (2*np.pi) - np.pi


def validate(x, sr):
    x = np.asarray(x)
    if x.ndim != 2 or x.shape[1] not in (1, 2) or sr not in (44100, 48000):
        raise ValueError("Expected frames x 1/2 channels at 44100/48000 Hz")
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite input: offline render rejected, state not retained")
    return x


def stft(x, cfg=Config()):
    """Left virtual silence plus full right flush; periodic Hann, double WOLA."""
    left = cfg.frame - cfg.hop
    count = int(np.ceil(len(x)/cfg.hop)) + cfg.frame//cfg.hop - 1
    padded = np.pad(x, ((left, cfg.frame), (0, 0)))
    w = .5-.5*np.cos(2*np.pi*np.arange(cfg.frame)/cfg.frame)
    frames = np.stack([padded[i*cfg.hop:i*cfg.hop+cfg.frame]
                       for i in range(count)]) if count else np.empty((0,cfg.frame,x.shape[1]))
    return np.fft.rfft(frames*w[None,:,None], axis=1).transpose(0,2,1), frames, w


def istft(spectra, length, w, cfg=Config()):
    output = np.zeros(((len(spectra)-1)*cfg.hop+cfg.frame, spectra.shape[1]))
    weights = np.zeros(len(output))
    for n, X in enumerate(spectra):
        sl = slice(n*cfg.hop, n*cfg.hop+cfg.frame)
        output[sl] += np.fft.irfft(X, n=cfg.frame, axis=-1).T*w[:,None]
        weights[sl] += w*w
    output /= np.maximum(weights[:,None], 1e-12)
    left = cfg.frame-cfg.hop
    return output[left:left+length]


def analyze(x, sr, cfg=Config()):
    """All prediction features use previous observations only in frame order.

    Offline frames include their entire support: this is not a LIVE detector.
    State time labels are frame centers, not a claim of physical strike times.
    """
    x = validate(x, sr)
    X, frames, w = stft(x, cfg)
    A, phase = np.abs(X), np.angle(X)
    pooled = np.sqrt(np.mean(A*A, axis=1))
    bins = np.fft.rfftfreq(cfg.frame, 1/sr)
    band = (bins >= 80) & (bins <= 12000)
    omega = 2*np.pi*np.arange(A.shape[-1])/cfg.frame
    dt = cfg.hop/sr
    prev = np.zeros_like(pooled[0]); prev_phase = np.zeros_like(phase[0])
    prev_frequency = np.broadcast_to(omega, phase[0].shape).copy()
    prev_A = np.zeros_like(A[0]); memory = np.zeros_like(prev)
    previous_energy = cfg.silence_rms
    since = 10.; memory_active = False
    rows, states, histories, freqs, reliabilities = [], [], [], [], []
    for n in range(len(X)):
        p = pooled[n]
        # Nonoverlapping newest hop RMS: avoids counting overlapping energy twice.
        energy = float(np.sqrt(np.mean(frames[n,-cfg.hop:]**2)))
        quiet = energy < cfg.silence_rms and np.sqrt(np.mean(frames[n]**2)) < cfg.silence_rms
        log_change = np.log(max(energy,cfg.silence_rms)/max(previous_energy,cfg.silence_rms))
        flux = float(np.maximum(p[band]-prev[band],0).sum() /
                     max(prev[band].sum(), p[band].sum()*.05, cfg.floor))
        power = p[band]**2
        flat = float(np.exp(np.mean(np.log(power+cfg.floor**2))) /
                     max(np.mean(power+cfg.floor**2), cfg.floor**2))
        tonal = float(np.clip(1-flat,0,1))
        reliable = ((A[n] > np.max(A[n],axis=-1,keepdims=True)*cfg.reliability_ratio) &
                    (prev_A > np.max(prev_A,axis=-1,keepdims=True)*cfg.reliability_ratio) &
                    (A[n] > 1e-7) & band[None,:])
        residual = principal(phase[n]-prev_phase-omega[None,:]*cfg.hop)
        frequency = omega[None,:]+residual/cfg.hop
        prediction_error = principal(phase[n]-prev_phase-cfg.hop*prev_frequency)
        q = np.minimum(A[n],prev_A)**2*reliable
        coherence = float(np.sum(q*np.cos(prediction_error))/max(q.sum(),cfg.floor))
        confidence = tonal*max(0.,coherence) if np.any(reliable) and not quiet else 0.
        onset = float(np.clip(max(flux/cfg.onset_flux, log_change/np.log(2)),0,1))
        attack = onset if not quiet else 0.
        if attack >= .5:
            since = 0.
        else:
            since += dt
        bloom = np.exp(-since/cfg.bloom_s)*(1-attack)
        falling = float(np.clip(-log_change/(3*dt),0,1))  # log amplitude decay >=3/s
        overlap = attack*float(memory.sum() > .25*max(p.sum(),cfg.floor))*float(memory_active)
        weights = np.array([attack,bloom,confidence*(1-falling)*(1-bloom)*(1-attack),
                            falling*(1-attack),overlap, float(quiet)])
        if quiet:
            weights[:] = 0; weights[-1] = 1
            memory.fill(0); memory_active = False
        else:
            if weights.sum() < cfg.floor:
                weights[2] = 1  # uncertain sustain label; confidence still zero => dry
            rho = np.exp(-dt/(.02 if attack >= .5 else cfg.resonance_s))
            memory = rho*memory+(1-rho)*p
            memory_active = True
        weights /= weights.sum()
        rows.append([energy,flux,tonal,coherence,float(memory.sum()),confidence,attack,
                     log_change, float(quiet), float(np.sum(q*np.abs(prediction_error))/max(q.sum(),cfg.floor))])
        states.append(weights); histories.append(memory.copy()); freqs.append(frequency)
        reliabilities.append(reliable)
        prev,prev_A,prev_phase,prev_frequency,previous_energy=p.copy(),A[n].copy(),phase[n].copy(),frequency.copy(),energy
    return dict(X=X, A=A, pooled=pooled, features=np.array(rows), states=np.array(states),
                resonance=np.array(histories), frequency=np.array(freqs), reliable=np.array(reliabilities),
                window=w, time=(np.arange(len(X))*cfg.hop-cfg.frame+cfg.hop+cfg.frame/2)/sr)


def control_targets(analysis, mode, sr, cfg=Config()):
    g, f = analysis['states'], analysis['features']
    if mode == 'velvet': target = cfg.velvet_depth*(g[:,2]+.5*g[:,1]+.3*g[:,3])
    elif mode == 'legato': target = cfg.legato_depth*(g[:,3]+g[:,4])
    else: target = cfg.melt_depth*g[:,2]
    return target*f[:,5]*(1-f[:,6])


def render(x, sr, mode, variant='governed', cfg=Config(), analysis=None):
    """Exact Bypass/noop; fresh instance histories make discontinuities resettable.

    A discontinuity is handled by rendering segments independently. Cross-gap
    reconstruction or concealment is deliberately absent from this offline API.
    """
    x = validate(x,sr)
    if mode == 'bypass': return x.copy(), {}
    if mode not in MODES or variant not in VARIANTS: raise ValueError('Unknown research mode/variant')
    a = analyze(x,sr,cfg) if analysis is None else analysis
    maximum = getattr(cfg,mode+'_depth')
    target = control_targets(a,mode,sr,cfg)
    active = a['features'][:,8] == 0
    matched = float(np.mean(target[active])) if np.any(active) else 0.
    if variant == 'fixed': target = np.full_like(target,maximum)
    elif variant == 'fixed_matched': target = np.full_like(target,matched)
    elif variant == 'attack_gated': target = maximum*(1-a['features'][:,6])
    elif variant == 'shuffled': target = np.random.default_rng(cfg.seed).permutation(target)
    elif variant == 'noop': target = np.zeros_like(target)
    u, previous, limit_count, reset_count = [], 0., 0, 0
    for n, value in enumerate(target):
        # Fixed controls still obey silence; shuffled controls retain independent attack safety.
        protected = variant in ('governed','attack_gated','shuffled')
        reset = not active[n] or (protected and a['features'][n,6] >= .5)
        uncertain = variant in ('governed','shuffled') and a['features'][n,5] < .2
        if reset or uncertain:
            current = 0.; reset_count += 1
        else:
            delta = maximum*(cfg.hop/sr)/cfg.recovery_s
            current = float(np.clip(value, previous-delta,previous+delta))
            limit_count += abs(current-value) > 1e-12
        u.append(current); previous=current
    u = np.array(u)
    # No-op must be exact source identity, while reconstruction is tested separately.
    if not np.any(u):
        return x.copy(), dict(control=u, target=target, gain_limit_frames=0, rate_limit_frames=int(limit_count),
                              fallback_frames=int(reset_count), effective_depth=0., phase_max=0., gain_min=1.,gain_max=1.)
    out = a['X'].copy()
    frequency_hz = np.fft.rfftfreq(cfg.frame,1/sr)
    W = frequency_hz**2/(frequency_hz**2+3000**2)
    memory = np.log(np.maximum(a['pooled'][0],cfg.floor))
    tracked = a['frequency'][0].copy(); phase_offset=np.zeros(out.shape[-1])
    gain_min, gain_max, phase_max, caps = 1.,1.,0.,0
    for n in range(len(out)):
        p=a['pooled'][n]; L=np.log(np.maximum(p,cfg.floor))
        attack=a['features'][n,6] >= .5
        silence=not active[n]
        if silence or (attack and variant in ('governed','attack_gated','shuffled')):
            memory=L.copy(); tracked=a['frequency'][n].copy(); phase_offset.fill(0)
        support=(p > max(p.max()*cfg.reliability_ratio,1e-7))
        gain=np.ones_like(p)
        if mode == 'velvet':
            K=np.zeros_like(L); K[1:-1]=L[:-2]-2*L[1:-1]+L[2:]
            peak=np.zeros_like(p,dtype=bool);peak[1:-1]=(p[1:-1]>=p[:-2])&(p[1:-1]>=p[2:])
            mask=np.where(peak,.25,1.)*support
            gain=np.exp(u[n]*W*mask*np.clip(K,-1,1))
        elif mode == 'legato':
            rho=np.exp(-(cfg.hop/sr)/cfg.legato_memory_s)
            memory=rho*memory+(1-rho)*L
            # Existing supported bins only, max .08 s memory, no invented tails.
            gain=np.exp(u[n]*support*np.clip(memory-L,-.6,.6))
        else:
            rho=np.exp(-(cfg.hop/sr)/cfg.melt_frequency_s)
            tracked=rho*tracked+(1-rho)*a['frequency'][n]
            q=a['A'][n]**2*a['reliable'][n]
            correction=np.sum(q*(tracked-a['frequency'][n]),axis=0)/np.maximum(q.sum(axis=0),cfg.floor)
            # Smooth bounded phase curvature; no magnitude-history interpolation.
            candidate=np.exp(-(cfg.hop/sr)/.08)*phase_offset+u[n]*cfg.hop*correction
            phase_offset=np.clip(candidate,-cfg.phase_max_rad,cfg.phase_max_rad)
            phase_offset*=support*np.any(a['reliable'][n],axis=0)*(frequency_hz>=500)*(u[n]>0)
            phase_offset[0]=phase_offset[-1]=0
            out[n]*=np.exp(1j*phase_offset)[None,:]
            phase_max=max(phase_max,float(np.max(np.abs(phase_offset))))
        clipped=np.clip(gain,cfg.gain_min,cfg.gain_max)
        caps+=int(np.any(clipped != gain))
        gain_min=min(gain_min,float(clipped.min()));gain_max=max(gain_max,float(clipped.max()))
        out[n]*=clipped[None,:]
    y=istft(out,len(x),a['window'],cfg)
    if not np.isfinite(y).all(): raise FloatingPointError('Nonfinite output rejected')
    return y,dict(control=u,target=target,gain_limit_frames=caps,rate_limit_frames=int(limit_count),
                  fallback_frames=int(reset_count),effective_depth=float(np.mean(u[active])) if active.any() else 0.,
                  phase_max=phase_max,gain_min=gain_min,gain_max=gain_max)
