"""Bounded-state worker implementation of the frozen Experiment 02 equations.

Frame n becomes available after its newest hop arrives. WOLA emits its oldest
hop, with 1536 samples of signal delay. No full-file render, chunk resets or DSP
in a PortAudio callback. See tests against the unchanged offline authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from isla.remastered import CORE_SHA256, RenderRequest


class RemasteredStreamingDSP:
    hop, window_size, delay = 512, 2048, 1536
    modes = ('velvet', 'legato', 'melt')

    def __init__(self, samplerate, channels, intensity=100):
        from tools.resonance02 import core
        if samplerate not in (44100, 48000) or channels not in (1, 2):
            raise ValueError('Remastered LIVE requires mono/stereo at 44.1/48 kHz.')
        if hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest() != CORE_SHA256:
            raise ValueError('Experiment 02 core differs from its freeze.')
        self.principal = core.principal
        self.cfg = core.Config()
        self.sr, self.channels, self.mode = samplerate, channels, 'bypass'
        self.set_intensity(intensity)
        self.dt = self.hop / samplerate
        self.window = .5-.5*np.cos(2*np.pi*np.arange(self.window_size)/self.window_size)
        self.history = np.zeros((self.window_size, channels), np.float32)
        bins = self.window_size//2+1
        self.hz = np.fft.rfftfreq(self.window_size, 1/samplerate)
        self.band = (self.hz >= 80) & (self.hz <= 12000)
        self.omega = 2*np.pi*np.arange(bins)/self.window_size
        self.W = self.hz**2/(self.hz**2+3000**2)
        self.prev_p = np.zeros(bins)
        self.prev_A = np.zeros((channels, bins))
        self.prev_phase = np.zeros((channels, bins))
        self.prev_frequency = np.broadcast_to(self.omega, (channels, bins)).copy()
        self.resonance = np.zeros(bins)
        self.previous_energy, self.since, self.memory_active = self.cfg.silence_rms, 10., False
        self.log_memory = self.tracked = None
        self.phase_offset = np.zeros(bins)
        self.control = np.zeros(3)
        self.tails = np.zeros((3, self.window_size, channels))
        self.weights = np.zeros(self.window_size)
        self.dry = np.zeros((self.delay, channels), np.float32)
        self.mix = np.array([1., 0., 0., 0.])
        self.fade = np.minimum(1., (np.arange(self.hop)+1)/round(.005*samplerate))[:, None]
        self.frames = self.vetoed = 0
        self.control_sum = np.zeros(3)
        self.control_max = np.zeros(3)
        self.peak = 0.
        self.last_features = self.last_states = None
        self.last_target = np.zeros(3)
        self.last_gain_range, self.last_phase_max = (1., 1.), 0.
        self.last_gain_ranges = np.ones((3,2))

    def set_intensity(self, intensity):
        # Each bank gets a separate immutable configuration with only its own
        # depth changed. Analysis constants and ceilings never change.
        self.configurations = tuple(RenderRequest(mode, intensity).configuration() for mode in self.modes)
        self.intensity = intensity

    def select(self, mode):
        if mode not in ('bypass', *self.modes):
            raise ValueError('Choose bypass, velvet, legato or melt.')
        self.mode = mode

    def _analyze(self, X):
        cfg = self.cfg
        A, phase = np.abs(X), np.angle(X)
        p = np.sqrt(np.mean(A*A, axis=0))
        energy = float(np.sqrt(np.mean(self.history[-self.hop:]**2)))
        quiet = energy < cfg.silence_rms and np.sqrt(np.mean(self.history**2)) < cfg.silence_rms
        log_change = np.log(max(energy,cfg.silence_rms)/max(self.previous_energy,cfg.silence_rms))
        flux = float(np.maximum(p[self.band]-self.prev_p[self.band],0).sum() /
                     max(self.prev_p[self.band].sum(),p[self.band].sum()*.05,cfg.floor))
        power = p[self.band]**2
        flat = float(np.exp(np.mean(np.log(power+cfg.floor**2))) /
                     max(np.mean(power+cfg.floor**2),cfg.floor**2))
        tonal = float(np.clip(1-flat,0,1))
        reliable = ((A > np.max(A,axis=-1,keepdims=True)*cfg.reliability_ratio) &
                    (self.prev_A > np.max(self.prev_A,axis=-1,keepdims=True)*cfg.reliability_ratio) &
                    (A > 1e-7) & self.band[None,:])
        residual = self.principal(phase-self.prev_phase-self.omega[None,:]*self.hop)
        frequency = self.omega[None,:]+residual/self.hop
        error = self.principal(phase-self.prev_phase-self.hop*self.prev_frequency)
        q = np.minimum(A,self.prev_A)**2*reliable
        coherence = float(np.sum(q*np.cos(error))/max(q.sum(),cfg.floor))
        confidence = tonal*max(0.,coherence) if np.any(reliable) and not quiet else 0.
        attack = float(np.clip(max(flux/cfg.onset_flux,log_change/np.log(2)),0,1)) if not quiet else 0.
        self.since = 0. if attack >= .5 else self.since+self.dt
        bloom = np.exp(-self.since/cfg.bloom_s)*(1-attack)
        falling = float(np.clip(-log_change/(3*self.dt),0,1))
        overlap = attack*float(self.resonance.sum() > .25*max(p.sum(),cfg.floor))*float(self.memory_active)
        g = np.array([attack,bloom,confidence*(1-falling)*(1-bloom)*(1-attack),
                      falling*(1-attack),overlap,float(quiet)])
        if quiet:
            g[:] = 0; g[-1] = 1
            self.resonance.fill(0); self.memory_active = False
        else:
            if g.sum() < cfg.floor:
                g[2] = 1
            rho = np.exp(-self.dt/(.02 if attack >= .5 else cfg.resonance_s))
            self.resonance = rho*self.resonance+(1-rho)*p
            self.memory_active = True
        g /= g.sum()
        self.last_features = np.array([energy,flux,tonal,coherence,float(self.resonance.sum()),
            confidence,attack,log_change,float(quiet),float(np.sum(q*np.abs(error))/max(q.sum(),cfg.floor))])
        self.last_states = g
        self.prev_p,self.prev_A,self.prev_phase,self.prev_frequency,self.previous_energy = p,A,phase,frequency,energy
        return A,p,frequency,reliable,confidence,attack,quiet,g

    def process_block(self, block):
        block = np.asarray(block, dtype=np.float32)
        if block.shape != (self.hop,self.channels) or not np.isfinite(block).all():
            raise ValueError('Remastered LIVE needs one finite 512-sample hop.')
        cfg = self.cfg
        self.history[:-self.hop] = self.history[self.hop:]
        self.history[-self.hop:] = block
        X = np.fft.rfft(self.history*self.window[:,None],axis=0).T
        A,p,frequency,reliable,h,attack,quiet,g = self._analyze(X)
        L = np.log(np.maximum(p,cfg.floor))
        if self.log_memory is None:
            self.log_memory, self.tracked = L.copy(), frequency.copy()
        if quiet or attack >= .5:
            self.log_memory, self.tracked = L.copy(), frequency.copy()
            self.phase_offset.fill(0)
        veto = quiet or attack >= .5 or h < .2
        support = p > max(p.max()*cfg.reliability_ratio,1e-7)
        self.weights += self.window**2
        gain_min,gain_max,phase_max = 1.,1.,0.
        targets = []
        for i,(mode,config) in enumerate(zip(self.modes,self.configurations)):
            maximum = getattr(config,mode+'_depth')
            regime = (g[2]+.5*g[1]+.3*g[3]) if i == 0 else (g[3]+g[4]) if i == 1 else g[2]
            target = maximum*regime*h*(1-attack)
            targets.append(target)
            delta = maximum*self.dt/cfg.recovery_s
            # A newly reduced user authority cap applies immediately; ordinary
            # fixed-setting motion retains the frozen 100 ms recovery rule.
            self.control[i] = 0. if veto else min(maximum,float(np.clip(
                target,self.control[i]-delta,self.control[i]+delta)))
            u = self.control[i]
            out, gain = X.copy(), np.ones_like(p)
            if mode == 'velvet':
                K = np.zeros_like(L); K[1:-1] = L[:-2]-2*L[1:-1]+L[2:]
                peak = np.zeros_like(p,dtype=bool)
                peak[1:-1] = (p[1:-1]>=p[:-2]) & (p[1:-1]>=p[2:])
                gain = np.exp(u*self.W*np.where(peak,.25,1.)*support*np.clip(K,-1,1))
            elif mode == 'legato':
                rho = np.exp(-self.dt/cfg.legato_memory_s)
                self.log_memory = rho*self.log_memory+(1-rho)*L
                gain = np.exp(u*support*np.clip(self.log_memory-L,-.6,.6))
            else:
                rho = np.exp(-self.dt/cfg.melt_frequency_s)
                self.tracked = rho*self.tracked+(1-rho)*frequency
                q = A**2*reliable
                correction = np.sum(q*(self.tracked-frequency),axis=0)/np.maximum(q.sum(axis=0),cfg.floor)
                candidate = np.exp(-self.dt/.08)*self.phase_offset+u*self.hop*correction
                self.phase_offset = np.clip(candidate,-cfg.phase_max_rad,cfg.phase_max_rad)
                self.phase_offset *= support*np.any(reliable,axis=0)*(self.hz>=500)*(u>0)
                self.phase_offset[0] = self.phase_offset[-1] = 0
                out *= np.exp(1j*self.phase_offset)[None,:]
                phase_max = float(np.max(np.abs(self.phase_offset)))
            clipped = np.clip(gain,cfg.gain_min,cfg.gain_max)
            self.last_gain_ranges[i] = clipped.min(),clipped.max()
            gain_min,gain_max = min(gain_min,float(clipped.min())),max(gain_max,float(clipped.max()))
            out *= clipped[None,:]
            self.tails[i] += np.fft.irfft(out,n=self.window_size,axis=-1).T*self.window[:,None]
        wet = self.tails[:,:self.hop]/np.maximum(self.weights[:self.hop,None],1e-12)
        dry = self.dry[:self.hop].copy()
        self.dry[:-self.hop] = self.dry[self.hop:]
        self.dry[-self.hop:] = block
        target_mix = np.zeros(4)
        target_mix[0 if self.mode == 'bypass' or self.intensity == 0 else self.modes.index(self.mode)+1] = 1
        if target_mix[0] and self.mix[0] == 1:
            result = dry  # Bit-exact delayed Bypass/zero, including signed zero.
        else:
            banks = np.concatenate((dry[None],wet),axis=0)
            mix = self.mix[None]+self.fade*(target_mix-self.mix)[None]
            result = np.einsum('mhc,hm->hc',banks,mix).astype(np.float32)
        self.mix = target_mix
        self.tails[:,:-self.hop] = self.tails[:,self.hop:]
        self.tails[:,-self.hop:] = 0
        self.weights[:-self.hop] = self.weights[self.hop:]
        self.weights[-self.hop:] = 0
        self.frames += 1; self.vetoed += int(veto)
        self.control_sum += self.control
        self.control_max = np.maximum(self.control_max,self.control)
        self.last_target = np.array(targets)
        self.last_gain_range,self.last_phase_max = (gain_min,gain_max),phase_max
        self.peak = max(self.peak,float(np.max(np.abs(result))))
        if not np.isfinite(result).all():
            raise ValueError('Remastered LIVE produced nonfinite audio; stopped safely.')
        return result
