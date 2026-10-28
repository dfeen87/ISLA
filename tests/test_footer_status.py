from dataclasses import replace

import pytest

from isla.control import ControlService, UIState
from isla.footer_status import footer_status
from test_control import make_session


@pytest.fixture
def state():
    controller, *_ = make_session()
    service = ControlService(controller)
    try:
        yield service.snapshot()
    finally:
        service.shutdown()
        controller.close()


@pytest.mark.parametrize('mode', ['bypass', 'velvet', 'legato', 'melt'])
def test_idle_live_selection_is_visible_without_animation(state, mode):
    result = footer_status(replace(state, source='system', live_mode=mode))
    assert result.selected == mode and result.stage == 'Ready'
    assert not result.playing and not result.applied


def test_pending_selection_and_confirmed_motion_are_distinct(state):
    active = replace(state, source='system', live_active=True,
                     live_state=UIState.LIVE_RUNNING, live_mode='velvet',
                     live_applied_mode='velvet')
    result = footer_status(active, pending_mode='melt')
    assert (result.selected, result.applied, result.stage, result.playing) == (
        'melt', 'velvet', 'Switching', True)
    result = footer_status(replace(active, live_mode='melt', live_applied_mode='melt'))
    assert result.stage == 'Playing' and result.applied == 'melt'


@pytest.mark.parametrize('kind', ['recovering', 'failed', 'stopping', 'closing'])
def test_transport_interruptions_never_animate_as_healthy_playback(state, kind):
    active = replace(state, source='system', live_active=True,
                     live_state=UIState.LIVE_RUNNING, live_mode='melt', live_applied_mode='melt')
    if kind == 'recovering':
        active = replace(active, live_recovering=True)
    elif kind == 'failed':
        active = replace(active, live_failure_reason='capture interrupted')
    elif kind == 'stopping':
        active = replace(active, live_state=UIState.LIVE_STOPPING)
    result = footer_status(active, closing=kind == 'closing')
    assert not result.playing and not result.applied
    assert result.selected == 'melt'


def test_alive_requested_callback_and_paused_states_use_structured_fields(state):
    active = replace(state, source='file', duration=10, file_state=UIState.PLAYING,
                     file_mode='velvet', file_requested_effect='melt',
                     file_applied_effect='velvet', file_transition_pending=True,
                     alive_applied_mode='This diagnostics text must not be parsed')
    result = footer_status(active)
    assert result.selected == 'melt' and result.applied == 'velvet'
    assert result.stage == 'Switching' and result.playing
    paused = footer_status(replace(active, file_state=UIState.PAUSED))
    assert paused.selected == 'melt' and paused.stage == 'Paused' and not paused.playing
    remastered = footer_status(replace(active, file_requested_effect='remastered_legato',
        file_applied_effect='remastered_legato', file_transition_pending=False))
    assert remastered.selected == remastered.applied == 'legato'
    assert remastered.stage == 'Playing'
