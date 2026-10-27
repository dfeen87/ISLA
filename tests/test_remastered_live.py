"""Streaming equations, not a per-chunk invocation of the offline renderer."""
import threading

import numpy as np
import pytest

from isla.live import LiveMonitor
from isla.live_engine import LiveEngineDSP, LiveRequest, LiveSettings
from isla.monitor_gain import ListeningGainDSP, MonitorVolume
from isla.remastered import RenderRequest
from isla.remastered_streaming import RemasteredStreamingDSP
from tools.remastered_verify import fixture
from tools.resonance02 import core
from test_live import FakeBackend, wait_for, warmup


def stream_render(x, sr, mode, intensity):
    dsp = RemasteredStreamingDSP(sr,x.shape[1],intensity)
    dsp.select(mode)
    padded = np.pad(x,((0,(-len(x))%512+1536),(0,0)))
    output, features, states, controls = [],[],[],[]
    for block in padded.reshape(-1,512,x.shape[1]):
        output.append(dsp.process_block(block))
        features.append(dsp.last_features.copy())
        states.append(dsp.last_states.copy())
        controls.append(dsp.control.copy())
    return np.concatenate(output)[1536:1536+len(x)],dsp,np.array(features),np.array(states),np.array(controls)


@pytest.mark.parametrize('sr',[44100,48000])
@pytest.mark.parametrize('channels',[1,2])
@pytest.mark.parametrize('mode',core.MODES)
@pytest.mark.parametrize('intensity',[0,25,50,75,100])
def test_live_matrix_matches_frozen_offline_governed_renderer(sr,channels,mode,intensity):
    x = fixture(sr,channels)
    y,dsp,features,states,controls = stream_render(x,sr,mode,intensity)
    cfg = RenderRequest(mode,intensity).configuration()
    expected,report = core.render(x,sr,mode,cfg=cfg)
    analysis = core.analyze(x,sr)
    np.testing.assert_allclose(features,analysis['features'],atol=2e-12,rtol=0)
    np.testing.assert_allclose(states,analysis['states'],atol=2e-12,rtol=0)
    np.testing.assert_allclose(controls[:,core.MODES.index(mode)],report['control'],atol=1e-14,rtol=0)
    np.testing.assert_allclose(y,expected.astype(np.float32),atol=1e-7,rtol=0)
    replay,*_ = stream_render(x,sr,mode,intensity)
    assert y.tobytes() == replay.tobytes()
    if intensity == 0:
        assert y.tobytes() == x.tobytes()
    assert dsp.last_gain_range[0] >= .8 and dsp.last_gain_range[1] <= 1.188502227
    assert dsp.last_phase_max <= .1 and dsp.vetoed > 0


@pytest.mark.parametrize('relation',['same','opposite','silent'])
@pytest.mark.parametrize('mode',core.MODES)
def test_live_stereo_relations_gaps_and_no_invented_tails(relation,mode):
    mono = fixture(48000,1)[:,0]
    x = np.column_stack((mono,mono if relation == 'same' else -mono if relation == 'opposite' else mono*0))
    for intensity in (0,25,50,75,100):
        y,*_ = stream_render(x,48000,mode,intensity)
        if relation == 'same': assert np.array_equal(y[:,0],y[:,1])
        elif relation == 'opposite': assert np.array_equal(y[:,0],-y[:,1])
        else: assert not np.count_nonzero(y[:,1])
        assert np.max(np.abs(y[37920:40800])) < 1e-10


def test_live_authority_changes_are_atomic_bounded_and_zero_is_original():
    d = RemasteredStreamingDSP(48000,2)
    d.select('melt')
    x = fixture(48000,2)
    for block in x[:512*60].reshape(-1,512,2): d.process_block(block)
    d.set_intensity(5)
    for _ in range(4):
        d.process_block(x[:512])
        assert np.all(d.control <= np.array([.16,.3,.3])*.05)
    d.set_intensity(0)
    d.process_block(x[:512])  # Existing bounded transition to exact dry.
    result = d.process_block(x[:512])
    assert not d.control.any()
    assert result.dtype == np.float32
    with pytest.raises(ValueError): d.set_intensity(7)
    with pytest.raises(ValueError): LiveRequest('remastered',51)
    with pytest.raises(ValueError): LiveRequest('unknown',50)


def test_worker_engine_warms_before_aligned_switch_and_preserves_production_output():
    from isla.streaming import StreamingDSP
    settings = LiveSettings()
    d = LiveEngineDSP(48000,2,settings)
    reference = StreamingDSP(48000,2)
    block = np.full((512,2),.1,np.float32)
    for _ in range(6):
        assert np.array_equal(d.process_block(block),reference.process_block(block))
    assert d.research is None
    settings.set('remastered',50)
    for _ in range(3):
        assert np.array_equal(d.process_block(block),reference.process_block(block))
        assert d.applied.engine == 'production'
    assert np.isfinite(d.process_block(block)).all()
    assert d.applied == LiveRequest('remastered',50)
    assert d.delay == 1536 and d.research is not None
    assert '50%' in d.diagnostics
    # Static Bypass is identical across engines despite the engine transition.
    np.testing.assert_array_equal(d.process_block(block),block)
    settings.set('production',50)
    d.process_block(block)
    assert d.applied.engine == 'production'
    assert d.research is None and d._research_hops == 0
    settings.set('remastered',50)
    for _ in range(3):
        d.process_block(block)
        assert d.applied.engine == 'production'
    assert d.applied.engine == 'production'
    d.process_block(block)
    assert d.applied.engine == 'remastered'


@pytest.mark.parametrize('rate',[44100,48000])
@pytest.mark.parametrize('mode',['bypass','velvet','legato','melt'])
def test_worker_retires_idle_remastered_only_after_fade_and_rewarms_on_reentry(rate,mode,monkeypatch):
    from isla.streaming import StreamingDSP
    calls = []
    original_process = RemasteredStreamingDSP.process_block
    def track(self,block):
        calls.append(self)
        return original_process(self,block)
    monkeypatch.setattr(RemasteredStreamingDSP,'process_block',track)

    settings = LiveSettings()
    d = LiveEngineDSP(rate,2,settings)
    reference = StreamingDSP(rate,2)
    d.select(mode); reference.select(mode)
    block = np.full((512,2),.02,np.float32)

    for _ in range(6):
        np.testing.assert_array_equal(d.process_block(block),reference.process_block(block))
    assert not calls and d.research is None

    settings.set('remastered',50)
    for hop in range(6):
        actual = d.process_block(block)
        dry = reference.process_block(block)
        if hop < 3:
            np.testing.assert_array_equal(actual,dry)
            assert d.applied.engine == 'production'
        else:
            assert d.applied.engine == 'remastered'
    prior = d.research
    assert prior is not None and calls and all(x is prior for x in calls)
    count = len(calls)

    settings.set('production',50)
    # This first return block still computes both outputs to preserve the
    # existing 5 ms crossfade; only AFTER its output is safe do we retire.
    returned = d.process_block(block)
    reference.process_block(block)
    assert returned.shape == block.shape and np.isfinite(returned).all()
    assert len(calls) == count+1
    assert d.applied.engine == 'production' and d.research is None
    assert d._research_hops == 0 and d._mix == 0
    count = len(calls)

    # No idle research blocks; Production output remains bit-exact and its
    # continuing historical state matches a permanently active reference.
    for _ in range(16):
        np.testing.assert_array_equal(d.process_block(block),reference.process_block(block))
    assert len(calls) == count

    settings.set('remastered',50)
    for hop in range(3):
        np.testing.assert_array_equal(d.process_block(block),reference.process_block(block))
        assert d.applied.engine == 'production'
        assert d.research is not prior
    assert len(calls) == count+3 and d._research_hops == 3
    output = d.process_block(block)
    reference.process_block(block)
    assert np.isfinite(output).all() and d.applied.engine == 'remastered'
    assert d.research is not prior and d._research_hops == 4


def test_live_processing_telemetry_counts_real_bank_work_and_releases_idle_bank():
    settings = LiveSettings()
    engine = LiveEngineDSP(48000,2,settings)
    audio = np.full((512,2),.01,np.float32)
    for _ in range(6):
        engine.process_block(audio)
    assert engine._processing_blocks == 6
    assert engine._research_blocks == 0
    assert engine._research_retirements == 0
    assert engine._total_last_ms >= engine._production_last_ms >= 0.
    assert 'Research bank: inactive / retired' in engine.processing_telemetry
    assert 'Nominal 512-frame interval: 10.67 ms' in engine.processing_telemetry

    settings.set('remastered',50)
    for _ in range(5):
        engine.process_block(audio)
    assert engine._research_blocks == 5
    assert 'Research bank: active / warming' in engine.processing_telemetry
    assert 'worker applied: Remastered' in engine.processing_telemetry
    settings.set('production',50)
    engine.process_block(audio)
    assert engine._research_blocks == 6
    assert engine._research_retirements == 1
    assert engine._research_last_ms > 0.
    assert engine._research_peak_ms > 0.
    for _ in range(20):
        engine.process_block(audio)
    assert engine._research_blocks == 6
    assert engine._research_last_ms == 0.
    assert engine._processing_blocks == 32
    assert 'Research bank: inactive / retired' in engine.processing_telemetry
    assert 'Remastered bank retirements: 1' in engine.processing_telemetry


def test_cancel_research_warmup_releases_unapplied_history():
    settings = LiveSettings()
    d = LiveEngineDSP(48000,2,settings)
    block = np.full((512,2),.03,np.float32)
    settings.set('remastered',25)
    for _ in range(2):
        d.process_block(block)
        assert d.applied.engine == 'production'
    unfinished = d.research
    assert unfinished is not None
    settings.set('production',25)
    d.process_block(block)
    assert d.research is None and d._research_hops == 0
    settings.set('remastered',25)
    d.process_block(block)
    assert d.research is not unfinished and d._research_hops == 1


def test_real_live_worker_owns_remastered_fft_and_reseeds_after_stop(monkeypatch):
    backend, settings, volume = FakeBackend(),LiveSettings(),MonitorVolume()
    settings.set('remastered',100)
    gate = threading.Event(); gate.set()
    owners = []
    original = RemasteredStreamingDSP.process_block
    def track(self,block):
        owners.append(threading.get_ident())
        return original(self,block)
    monkeypatch.setattr(RemasteredStreamingDSP,'process_block',track)
    class Scheduled(ListeningGainDSP):
        def process_block(self,block):
            assert gate.wait(5)
            return super().process_block(block)
    monitor = LiveMonitor(backend,processor_factory=lambda rate,channels: Scheduled(
        rate,channels,volume,delegate_factory=lambda r,c: LiveEngineDSP(r,c,settings)),
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.)
    try:
        monitor.start('BlackHole 2ch','Test speakers')
        warmup(monitor)
        monitor.select('melt')
        x = fixture(48000,2)
        for block in x[:512*20].reshape(-1,512,2):
            gate.clear()
            try: monitor.stream.pump(block)
            finally: gate.set()
            wait_for(lambda: monitor.output.count == 1 or monitor.halt.is_set(),timeout=5)
            assert not monitor.halt.is_set(),monitor.error
        engine = monitor.processor.delegate
        assert engine.applied.engine == 'remastered'
        assert engine.research.frames == 20
        assert set(owners) == {monitor.worker.ident}
        assert threading.get_ident() not in owners
        assert monitor.input.high_water <= 8 and monitor.output.high_water <= 8
        monitor.stop()
        monitor.start('BlackHole 2ch','Test speakers')
        assert monitor.processor.delegate.research is None
    finally:
        gate.set(); monitor.stop()


@pytest.mark.parametrize('rate',[44100,48000])
@pytest.mark.parametrize('mode',core.MODES)
def test_real_remastered_worker_capture_recovery_matches_fresh_engine(rate,mode):
    from test_live_recovery import session,pump,recover
    settings = LiveSettings(); settings.set('remastered',75)
    class Engine(LiveEngineDSP):
        def __init__(self,r,c): super().__init__(r,c,settings)
    with session(Engine,rate) as (monitor,stream):
        monitor.select(mode)
        for _ in range(10): pump(monitor,stream,np.full((512,2),-.1,np.float32))
        old = monitor.processor.research
        recover(monitor,stream)
        assert monitor.processor.research is None and old is not None
        reference = Engine(rate,2); reference.select(mode)
        expected,actual = [],[]
        for _ in range(12):
            block = np.full((512,2),.1,np.float32)
            expected.append(reference.process_block(block))
            actual.append(pump(monitor,stream,block))
        np.testing.assert_array_equal(np.concatenate(actual[1:]),np.concatenate(expected[:-1]))
        assert monitor.recoveries == 1 and monitor.failed_recoveries == 0


def test_terminal_and_window_share_live_engine_settings_and_factory():
    from test_control import selected_service
    service,c,_,_,_,_ = selected_service()
    try:
        service.set_live_processing('remastered',50)
        assert c.live_settings.request == LiveRequest('remastered',50)
        service.shutdown()
        assert 'Remastered' in c.execute('engine remastered 75')
        assert c.live_settings.request == LiveRequest('remastered',75)
        c.execute('monitor start')
        assert isinstance(c.live.processor,LiveEngineDSP)
        assert c.live.processor.settings is c.live_settings
        assert 'remastered' in c.execute('status')
        c.execute('engine production')
        assert c.live_settings.request.engine == 'production'
        with pytest.raises(ValueError): c.execute('engine remastered 7')
        with pytest.raises(ValueError): c.execute('engine remastered loud')
    finally:
        if not service.closed: service.shutdown()
        c.close()
