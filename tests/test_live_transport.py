"""Application transport ownership, concurrent copies and retained audio guards."""
import ast
import inspect
import threading
import time
from textwrap import dedent
from types import SimpleNamespace

import numpy as np
import pytest

from isla.live import BLOCK,CAPACITY,BlockRing,LiveMonitor
from isla.live_transport import ReliableLiveMonitor,SingleProducerConsumerRing
from isla.playback import AudioError
from test_live import FakeBackend,PassThrough,wait_for,warmup
import test_live_recovery as recovery


def test_legacy_copy_mutex_reproduces_reported_false_capacity_failure():
    ring=BlockRing(2)
    block=np.full((BLOCK,2),.25,np.float32)
    assert ring.push(block,1.)
    with ring.lock:  # The legacy consumer holds this same lock while copying.
        assert not ring.push(block,2.)
    assert ring.count==1 and ring.last_push_failure=='lock contention'
    assert ring.high_water<CAPACITY


def test_consumer_copy_does_not_block_producer_or_allow_slot_overwrite(monkeypatch):
    ring=SingleProducerConsumerRing(2,capacity=2)
    first=np.full((BLOCK,2),.25,np.float32)
    second=np.full_like(first,.5)
    target=np.empty_like(first)
    entered,release=threading.Event(),threading.Event()
    copy=np.copyto
    def held_copy(destination,source,*args,**kwargs):
        if destination is target:
            entered.set()
            assert release.wait(2)
        return copy(destination,source,*args,**kwargs)
    monkeypatch.setattr(np,'copyto',held_copy)
    assert ring.push(first,1.)
    result=[]
    consumer=threading.Thread(target=lambda:result.append(ring.pop_into(target)))
    consumer.start()
    try:
        assert entered.wait(1)
        assert ring.push(second,2.), 'A different free slot must remain writable during consumer copy.'
        assert not ring.push(second,3.), 'The slot still being copied cannot be overwritten.'
        assert ring.last_push_failure=='queue full'
    finally:
        release.set();consumer.join(2)
    assert not consumer.is_alive() and result==[1.]
    np.testing.assert_array_equal(target,first)
    assert ring.pop_into(target)==2.
    np.testing.assert_array_equal(target,second)
    assert ring.count==0 and ring.high_water==2


def test_incomplete_producer_copy_is_not_published_to_consumer(monkeypatch):
    ring=SingleProducerConsumerRing(2)
    block=np.full((BLOCK,2),.25,np.float32)
    target=np.full_like(block,-1)
    entered,release=threading.Event(),threading.Event()
    copy=np.copyto
    def held_copy(destination,source,*args,**kwargs):
        if source is block:
            entered.set();assert release.wait(2)
        return copy(destination,source,*args,**kwargs)
    monkeypatch.setattr(np,'copyto',held_copy)
    producer=threading.Thread(target=lambda:ring.push(block,12.))
    producer.start()
    try:
        assert entered.wait(1)
        assert ring.pop_into(target) is None
        np.testing.assert_array_equal(target,-1)
    finally:
        release.set();producer.join(2)
    assert ring.pop_into(target)==12.
    np.testing.assert_array_equal(target,block)


def test_concurrent_fifo_wraps_without_torn_blocks_or_storage_growth():
    ring=SingleProducerConsumerRing(2)
    storage=(ring.data,ring.stamps)
    total=3000
    failures=[]
    def produce():
        block=np.empty((BLOCK,2),np.float32)
        deadline=time.monotonic()+10
        for index in range(total):
            block.fill(index)
            while not ring.push(block,float(index)):
                if time.monotonic()>deadline:
                    failures.append('producer timeout');return
                time.sleep(0)
    producer=threading.Thread(target=produce)
    producer.start()
    target=np.empty((BLOCK,2),np.float32)
    try:
        for index in range(total):
            deadline=time.monotonic()+10
            while (stamp:=ring.pop_into(target)) is None:
                assert time.monotonic()<deadline
                time.sleep(0)
            assert stamp==float(index)
            np.testing.assert_array_equal(target,index)
    finally:
        producer.join(10)
    assert not failures and not producer.is_alive() and ring.count==0
    assert ring.data is storage[0] and ring.stamps is storage[1]
    assert ring.high_water<=CAPACITY


def test_discard_keeps_storage_and_never_replays_old_slots():
    ring=SingleProducerConsumerRing(2)
    target=np.empty((BLOCK,2),np.float32)
    old=np.full_like(target,-.5)
    for stamp in range(3):
        assert ring.push(old,float(stamp))
    storage=ring.data
    assert ring.discard()==3 and ring.pop_into(target) is None
    assert ring.push(np.full_like(target,.25),7.)
    assert ring.pop_into(target)==7.
    np.testing.assert_array_equal(target,.25)
    assert ring.data is storage


def test_application_monitor_preserves_startup_lifecycle_and_all_guard_methods():
    original=ast.parse(dedent(inspect.getsource(LiveMonitor.start)))
    adapted=ast.parse(dedent(inspect.getsource(ReliableLiveMonitor.start)))
    for node in ast.walk(adapted):
        if isinstance(node,ast.Name) and node.id=='_application_ring':
            node.id='BlockRing'
    assert ast.dump(original,include_attributes=False)==ast.dump(adapted,include_attributes=False)
    for name in ('_callback','_work','_fault','_validate_devices','_release','stop'):
        assert getattr(ReliableLiveMonitor,name) is getattr(LiveMonitor,name)


@pytest.mark.parametrize('rate',[44100,48000])
@pytest.mark.parametrize('mode',['bypass','velvet','legato','melt'])
def test_application_rings_preserve_fresh_dsp_audio_after_capture_recovery(monkeypatch,rate,mode):
    monkeypatch.setattr(recovery,'LiveMonitor',ReliableLiveMonitor)
    recovery.test_isolated_gap_discards_history_matches_fresh_dsp_and_finite_peak(mode,rate)


@pytest.mark.parametrize('persistent',[False,True])
def test_application_repeated_capture_loss_still_stops(monkeypatch,persistent):
    monkeypatch.setattr(recovery,'LiveMonitor',ReliableLiveMonitor)
    recovery.test_repeated_or_persistent_capture_loss_fails_closed(persistent)


@pytest.mark.parametrize('defect',['disconnect','identity','routing'])
def test_application_native_guards_still_stop_recovery(monkeypatch,defect):
    monkeypatch.setattr(recovery,'LiveMonitor',ReliableLiveMonitor)
    recovery.test_native_identity_and_routing_guards_still_stop_pending_recovery(defect)


def test_application_real_queue_full_still_stops_and_retains_cause():
    entered,release=threading.Event(),threading.Event()
    class Held(PassThrough):
        def process_block(self,block):
            entered.set();assert release.wait(3)
            return super().process_block(block)
    backend=FakeBackend()
    monitor=ReliableLiveMonitor(backend,Held,monotonic_clock=lambda:0.)
    monitor.start('BlackHole 2ch','Test speakers')
    stream=monitor.stream
    zero=np.zeros((BLOCK,2),np.float32)
    try:
        warmup(monitor)
        # Keep output filled so input saturation is tested independently of
        # the monitor's unchanged output-starvation deadline.
        assert monitor.output.push(zero,stream.clock)
        stream.pump(zero)
        assert entered.wait(1)
        for _ in range(CAPACITY+1):
            assert monitor.output.push(zero,stream.clock)
            stream.pump(zero)
        assert monitor.halt.is_set() and monitor.input.last_push_failure=='queue full'
        assert monitor.input.high_water==CAPACITY and monitor.ring_failures==1
        assert 'Input buffer overflow' in monitor.error
    finally:
        release.set();monitor.stop()
    assert stream.closed


def test_runtime_without_gil_keeps_historical_synchronized_ring(monkeypatch):
    import isla.live_transport as transport
    monkeypatch.setattr(transport.sys,'_is_gil_enabled',lambda:False,raising=False)
    assert isinstance(transport._application_ring(2),BlockRing)


def test_application_native_start_handshake_still_survives_slow_device_start(monkeypatch):
    import test_live
    monkeypatch.setattr(test_live,'LiveMonitor',ReliableLiveMonitor)
    test_live.test_native_stream_start_latency_does_not_trigger_premature_watchdog()
