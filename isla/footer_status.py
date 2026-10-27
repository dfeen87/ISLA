"""Small, immutable presentation model shared with the telemetry snapshot."""
from dataclasses import dataclass

from isla.control import UIState


def effect_name(value):
    value = value.removeprefix('remastered_')
    if value in ('original', 'bypass'):
        return 'bypass'
    return value if value in ('velvet', 'legato', 'melt') else ''


@dataclass(frozen=True)
class FooterStatus:
    source: str = 'ISLA'
    selected: str = ''
    applied: str = ''
    stage: str = 'Connecting'
    playing: bool = False
    playback_percent: int = 100

    @property
    def caption(self):
        mode = 'Original' if self.selected == 'bypass' else self.selected.title()
        speed = '50%' if self.playback_percent == 50 else ''
        return ' · '.join(part for part in (self.source, mode, speed, self.stage) if part)


def footer_status(state, *, pending_mode=None, closing=False, stopping=False):
    if state is None:
        return FooterStatus()
    live = state.live_active or state.source == 'system'
    selected = effect_name(pending_mode or (state.live_mode if live else
                           state.file_requested_effect or state.file_mode))
    source = 'LIVE' if live else 'ALIVE'
    speed = 50 if not live and state.vinyl_slowdown else 100
    if closing or stopping:
        return FooterStatus(source, selected, stage='Stopping', playback_percent=speed)
    if live:
        if state.live_failure_reason or state.live_state == UIState.FATAL_ERROR:
            return FooterStatus(source, selected, stage='Stopped safely')
        if state.live_state == UIState.LIVE_STOPPING:
            return FooterStatus(source, selected, stage='Stopping')
        if not state.live_active:
            return FooterStatus(source, selected, stage='Ready')
        if state.live_recovering:
            return FooterStatus(source, selected, stage='Recovering')
        applied = effect_name(state.live_applied_mode or '')
        stage = 'Playing' if applied and applied == selected else 'Switching'
        return FooterStatus(source, selected, applied, stage,
                            state.live_state == UIState.LIVE_RUNNING)
    if state.file_state == UIState.PREPARING:
        return FooterStatus(source, stage='Preparing file')
    if not state.duration:
        return FooterStatus(source, stage='Open a file')
    if state.file_state != UIState.PLAYING:
        return FooterStatus(source, selected, stage=(
            'Paused' if state.file_state == UIState.PAUSED else 'Ready'), playback_percent=speed)
    applied = effect_name(state.file_applied_effect)
    stage = ('Playing' if applied and applied == selected and
             not state.file_transition_pending else 'Switching')
    return FooterStatus(source, selected, applied, stage, True, speed)
