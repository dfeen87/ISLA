"""Atomic UI requests and worker-only production/Remastered engine selection."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np

from isla.remastered import RenderRequest
from isla.streaming import StreamingDSP


@dataclass(frozen=True)
class LiveRequest:
    engine: str = 'production'
    intensity: int = 100

    def __post_init__(self):
        if self.engine not in ('production','remastered'):
            raise ValueError('Choose production or remastered LIVE processing.')
        RenderRequest('velvet',self.intensity)


class LiveSettings:
    def __init__(self):
        self.request = LiveRequest()

    def set(self, engine, intensity):
        self.request = LiveRequest(engine,intensity)


@dataclass(frozen=True)
class LiveEngineFactory:
    settings: LiveSettings
    production_factory: object = StreamingDSP

    def __call__(self,rate,channels):
        return LiveEngineDSP(rate,channels,self.settings,production_factory=self.production_factory)


def current_engine(processor):
    if isinstance(processor,LiveEngineDSP):
        return processor
    candidate = getattr(processor,'delegate',None)
    return candidate if isinstance(candidate,LiveEngineDSP) else None


class LiveEngineDSP:
    def __init__(self, rate, channels, settings, *, production_factory=StreamingDSP):
        self.production = production_factory(rate,channels)
        self.settings, self.rate, self.channels = settings,rate,channels
        self.research = None
        self._research_hops = 0
        self._mix = 0.
        self.applied = LiveRequest()
        self.diagnostics = 'Production LIVE harmonic profiles'
        # Scalar, best-effort worker-only observations. No per-block logs,
        # raw audio copies, mutable reporting containers, or callback reads.
        self._processing_blocks = self._research_blocks = 0
        self._research_retirements = self._budget_exceedances = 0
        self._production_last_ms = self._production_peak_ms = 0.
        self._research_last_ms = self._research_peak_ms = 0.
        self._total_last_ms = self._total_peak_ms = 0.

    @property
    def delay(self):
        return self.production.delay

    @property
    def mode(self):
        return self.production.mode

    def select(self, mode):
        self.production.select(mode)
        if self.research is not None:
            self.research.select(mode)

    @property
    def processing_telemetry(self):
        # Called outside the real-time worker by ControlService's polling
        # snapshot. Values may be slightly out of phase across threads.
        budget = 512 / self.rate * 1000
        return (
            'Requested engine: ' + self.settings.request.engine.title() +
            '; worker applied: ' + self.applied.engine.title() + '\n'
            'Research bank: ' + ('active / warming' if self.research is not None
                                 else 'inactive / retired') + '\n'
            f'Nominal 512-frame interval: {budget:.2f} ms at {self.rate:,} Hz\n'
            f'Worker DSP wall time last/peak: {self._total_last_ms:.3f} / '
            f'{self._total_peak_ms:.3f} ms\n'
            f'Production bank last/peak: {self._production_last_ms:.3f} / '
            f'{self._production_peak_ms:.3f} ms\n'
            f'Remastered bank last/peak: {self._research_last_ms:.3f} / '
            f'{self._research_peak_ms:.3f} ms\n'
            f'Worker DSP blocks / Remastered blocks: {self._processing_blocks} / '
            f'{self._research_blocks}\n'
            f'DSP intervals over nominal block budget: {self._budget_exceedances}; '
            f'Remastered bank retirements: {self._research_retirements}\n'
            'Measurements are approximate worker wall time, not CPU utilization '
            'or proof of native driver failure. See LIVE transport counters '
            'for capture/discontinuity and recovery evidence.'
        )

    def process_block(self, block):
        request = self.settings.request
        started = perf_counter()
        old = self.production.process_block(block)
        production_ms = (perf_counter() - started) * 1000
        if request.engine == 'remastered' and self.research is None:
            from isla.remastered_streaming import RemasteredStreamingDSP
            if self.delay != RemasteredStreamingDSP.delay:
                raise ValueError('LIVE engines must have the same delay before switching.')
            self.research = RemasteredStreamingDSP(self.rate,self.channels,request.intensity)
            self.research.select(self.mode)
        # Run the research bank only while requested or while finishing an
        # already-started transition back to Production. The first block of
        # that return still needs BOTH outputs for the existing 5 ms fade.
        # No PortAudio callback or frozen research algorithm is changed.
        new = None
        research_ms = 0.
        if self.research is not None and (request.engine == 'remastered' or self._mix):
            research_start = perf_counter()
            if self.research.intensity != request.intensity:
                self.research.set_intensity(request.intensity)
            new = self.research.process_block(block)
            research_ms = (perf_counter() - research_start) * 1000
            self._research_hops += 1
            self._research_blocks += 1
        ready = self.research is not None and self._research_hops > self.research.delay//self.research.hop
        target = float(request.engine == 'remastered' and ready)
        if target == self._mix:
            result = new if target else old
        else:
            n = min(len(old),max(2,round(self.rate*.005)))
            ramp = np.linspace(self._mix,target,n,dtype=np.float32)[:,None]
            result = (new if target else old).copy()
            result[:n] = old[:n]*(1-ramp)+new[:n]*ramp
        if ((target or self._mix) and self.mode != 'bypass' and request.intensity > 0
                and np.max(np.abs(result)) > 1.):
            raise ValueError('Remastered LIVE exceeded full scale; lower the source app volume and restart.')
        self._mix = target
        self.applied = request if target else LiveRequest('production',request.intensity)
        if request.engine == 'production' and not self._mix and self.research is not None:
            # Transition output has already been constructed and checked.
            # Retire inactive FFT/WOLA history on the DSP worker thread.
            # A later Remastered request must create a NEW bank and complete
            # its ordinary warmup rather than replaying stale musical history.
            self.research = None
            self._research_hops = 0
            self._research_retirements += 1
        if target:
            d = self.research
            index = d.modes.index(self.mode) if self.mode != 'bypass' else 0
            self.diagnostics = (f'Remastered LIVE {self.mode.title()} — {request.intensity}% permitted depth; '
                f'applied depth {d.control[index]:.4f}; vetoed {d.vetoed}/{d.frames} frames; '
                f'sample peak {d.peak:.5f}; 1536-sample DSP delay; REVISE / INCONCLUSIVE')
        else:
            self.diagnostics = ('Preparing Remastered LIVE history…' if request.engine == 'remastered'
                                else 'Production LIVE harmonic profiles')
        # No audio-thread I/O. These scalars describe work performed by this
        # worker, including OS scheduling interruptions and Python overhead.
        total_ms = (perf_counter() - started) * 1000
        self._processing_blocks += 1
        self._production_last_ms = production_ms
        self._production_peak_ms = max(self._production_peak_ms, production_ms)
        self._research_last_ms = research_ms
        self._research_peak_ms = max(self._research_peak_ms, research_ms)
        self._total_last_ms = total_ms
        self._total_peak_ms = max(self._total_peak_ms, total_ms)
        if total_ms > 512 / self.rate * 1000:
            self._budget_exceedances += 1
        return result
