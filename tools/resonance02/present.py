"""Render saved evidence and blank listening forms; never run candidate DSP."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, stft

SOURCES = ('recorded_piano', 'recorded_piano_reserved', 'connected_melody', 'harmonic_sustain')
MODES = ('velvet', 'legato', 'melt')
COLORS = {'bypass': '#303846', 'velvet_governed': '#b45b25',
          'legato_governed': '#087f8c', 'melt_governed': '#7151a0'}
REGIMES = ('Attack', 'Bloom', 'Sustain', 'Decay', 'Overlap', 'Silence')
REGIME_COLORS = ('#bd4f43', '#dfaa53', '#5b9e81', '#638cac', '#9574a8', '#d6d8dc')
QUESTIONS = ('discrimination', 'preference', 'smoothness', 'piano_character',
             'expressive_attacks', 'resonance_preservation', 'mode_distinctness', 'artifacts')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def label(name):
    return name.replace('_', ' ').capitalize()


def save(fig, folder, name, generated):
    fig.savefig(folder/(name+'.png'), dpi=180, bbox_inches='tight', facecolor='white')
    fig.savefig(folder/(name+'.svg'), bbox_inches='tight', facecolor='white', metadata={'Date': None})
    generated.extend((folder/(name+'.png'), folder/(name+'.svg')))
    plt.close(fig)


def load_audio(root, name, candidate):
    return sf.read(root/'raw'/name/(candidate+'.wav'), always_2d=True, dtype='float64')


def make_mode_distinctness(root):
    """Post-freeze cross-mode listening preparation, using saved raw files only."""
    root = Path(root)
    destination = root/'listening/mode_distinctness'
    key_path = root/'listening/MODE_DISTINCTNESS_KEY.json'
    trials = []
    if key_path.exists():
        key = read_json(key_path)
        for row in key['trials']:
            for side in ('A', 'B'):
                assert digest(root/row[side+'_path']) == row[side+'_sha256'], 'Supplement file changed'
            for candidate, expected in row['raw_input_sha256'].items():
                assert digest(root/'raw'/row['source']/(candidate+'.wav')) == expected, 'Supplement source changed'
        trials = key['trials']
    else:
        rng = np.random.default_rng(20261025)
        for source in SOURCES:
            for first, second in (('velvet', 'legato'), ('velvet', 'melt'), ('legato', 'melt')):
                names = [first+'_governed', second+'_governed']
                a, sr = load_audio(root, source, names[0])
                b, sr_b = load_audio(root, source, names[1])
                assert sr == sr_b and a.shape == b.shape
                rms_a, rms_b = np.sqrt(np.mean(a*a)), np.sqrt(np.mean(b*b))
                matching_gain = float(rms_a/rms_b) if rms_b > 1e-12 else 1.
                b = b*matching_gain
                pre_headroom_peak = max(np.max(np.abs(resample_poly(a, 4, 1, axis=0))),
                                        np.max(np.abs(resample_poly(b, 4, 1, axis=0))))
                common = min(1., .8/pre_headroom_peak) if pre_headroom_peak else 1.
                arrays, gains = [a*common, b*common], [common, common*matching_gain]
                hashes = {candidate: digest(root/'raw'/source/(candidate+'.wav')) for candidate in names}
                if rng.integers(2):
                    arrays.reverse(); names.reverse(); gains.reverse()
                trial = f'M{len(trials)+1:03d}'
                folder = destination/trial
                folder.mkdir(parents=True, exist_ok=False)
                row = dict(trial=trial, source=source, A=names[0], B=names[1],
                           gain_A=float(gains[0]), gain_B=float(gains[1]),
                           common_headroom_gain=float(common), pre_headroom_4x_peak=float(pre_headroom_peak),
                           rate=sr, frames=len(a), channels=a.shape[1], raw_input_sha256=hashes,
                           matching='One scalar RMS match plus common 4x estimated peak headroom; same gain in both channels; not perceptual loudness',
                           creator_listening='PENDING')
                for side, array in zip(('A', 'B'), arrays):
                    path = folder/(side+'.wav')
                    sf.write(path, array, sr, subtype='FLOAT')
                    row[side+'_path'] = path.relative_to(root).as_posix()
                    row[side+'_sha256'] = digest(path)
                    row[side+'_saved_4x_peak'] = float(np.max(np.abs(resample_poly(array.astype(np.float32), 4, 1, axis=0))))
                trials.append(row)
        key = dict(schema=1, registration='Supplementary creator-listening preparation after the primary freeze',
                   seed=20261025, creator_listening='PENDING', primary_BLIND_KEY_unchanged=True,
                   mechanism='Saved original-duration governed WAVs only; no DSP rerender or tuning', trials=trials)
        key_path.write_text(json.dumps(key, indent=2)+'\n')
    responses = root/'listening/MODE_DISTINCTNESS_RESPONSES.csv'
    if not responses.exists():
        with responses.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['trial', 'source', *QUESTIONS, 'notes', 'listener', 'session_date'])
            writer.writeheader()
            writer.writerows({'trial': row['trial'], 'source': row['source']} for row in trials)
    return [key_path, responses, *(root/row[side+'_path'] for row in trials for side in ('A', 'B'))]


def make_slowdown_listening(root):
    """Matched post-freeze auditions of an explicitly incomplete slowdown path."""
    root = Path(root)
    destination = root/'listening/slowdown_blind'
    key_path = root/'listening/SLOWDOWN_KEY.json'
    trials = []
    if key_path.exists():
        key = read_json(key_path)
        for row in key['trials']:
            for side in ('A', 'B'):
                assert digest(root/row[side+'_path']) == row[side+'_sha256'], 'Slowdown supplement file changed'
            for relative, expected in row['saved_slowdown_input_sha256'].items():
                assert digest(root/relative) == expected, 'Saved slowdown source changed'
        trials = key['trials']
    else:
        rng = np.random.default_rng(20261026)
        for source in ('recorded_piano', 'recorded_piano_reserved'):
            for ratio in (1.25, 1.50):
                prefix = f'{source}_r{ratio:.2f}_protected'
                for mode in MODES:
                    relatives = [f'slowdown/{prefix}.wav', f'slowdown/{prefix}_{mode}.wav']
                    names = ['protected_untreated_stretch', 'protected_stretch_plus_'+mode]
                    a, sr = sf.read(root/relatives[0], always_2d=True, dtype='float64')
                    b, sr_b = sf.read(root/relatives[1], always_2d=True, dtype='float64')
                    assert sr == sr_b and a.shape == b.shape
                    rms_a, rms_b = np.sqrt(np.mean(a*a)), np.sqrt(np.mean(b*b))
                    matching_gain = float(rms_a/rms_b) if rms_b > 1e-12 else 1.
                    b = b*matching_gain
                    pre_headroom_peak = max(np.max(np.abs(resample_poly(a, 4, 1, axis=0))),
                                            np.max(np.abs(resample_poly(b, 4, 1, axis=0))))
                    common = min(1., .8/pre_headroom_peak) if pre_headroom_peak else 1.
                    arrays, gains = [a*common, b*common], [common, common*matching_gain]
                    hashes = {relative: digest(root/relative) for relative in relatives}
                    if rng.integers(2):
                        arrays.reverse(); names.reverse(); gains.reverse(); relatives.reverse()
                    trial = f'S{len(trials)+1:03d}'
                    folder = destination/trial
                    folder.mkdir(parents=True, exist_ok=False)
                    row = dict(trial=trial, source=source, ratio=ratio, A=names[0], B=names[1],
                               A_input=relatives[0], B_input=relatives[1],
                               gain_A=float(gains[0]), gain_B=float(gains[1]),
                               common_headroom_gain=float(common), pre_headroom_4x_peak=float(pre_headroom_peak),
                               rate=sr, frames=len(a), channels=a.shape[1], saved_slowdown_input_sha256=hashes,
                               matching='One scalar RMS match plus common 4x estimated peak headroom; same gain in both channels; not perceptual loudness',
                               prototype_status='INCOMPLETE: underlying slowdown failed frozen transient timing/smear screen',
                               creator_listening='PENDING')
                    for side, array in zip(('A', 'B'), arrays):
                        path = folder/(side+'.wav')
                        sf.write(path, array, sr, subtype='FLOAT')
                        row[side+'_path'] = path.relative_to(root).as_posix()
                        row[side+'_sha256'] = digest(path)
                        row[side+'_saved_4x_peak'] = float(np.max(np.abs(resample_poly(array.astype(np.float32), 4, 1, axis=0))))
                    trials.append(row)
        key = dict(schema=1, registration='Supplementary slowed-piano listening preparation after the primary freeze',
                   seed=20261026, creator_listening='PENDING',
                   prototype_status='INCOMPLETE: frozen impulse timing and energy-spread failures remain',
                   mechanism='Saved protected slowdown WAVs only; untreated stretch versus stretch plus identity; no DSP rerender or tuning',
                   independent_factor='Slowdown listening does not establish original-duration identity improvement or a robust slowdown feature',
                   primary_BLIND_KEY_unchanged=True, trials=trials)
        key_path.write_text(json.dumps(key, indent=2)+'\n')
    responses = root/'listening/SLOWDOWN_RESPONSES.csv'
    if not responses.exists():
        with responses.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['trial', 'source', 'ratio', *QUESTIONS, 'notes', 'listener', 'session_date'])
            writer.writeheader()
            writer.writerows({'trial': row['trial'], 'source': row['source'], 'ratio': row['ratio']} for row in trials)
    return [key_path, responses, *(root/row[side+'_path'] for row in trials for side in ('A', 'B'))]


def passage_figures(root, folder, name, generated):
    candidates = ('bypass',) + tuple(mode+'_governed' for mode in MODES)
    audio = {c: load_audio(root, name, c) for c in candidates}
    sr = audio['bypass'][1]
    fig, axes = plt.subplots(5, 1, figsize=(9.4, 11.4), sharex=True,
                             gridspec_kw={'height_ratios': [1.1, 1, 1, 1, 1]}, layout='constrained')
    # One-millisecond extrema retain narrow waveform peaks in the overview.
    for c in candidates:
        x = audio[c][0][:, 0]
        width = max(1, round(sr*.001))
        blocks = x[:len(x)//width*width].reshape(-1, width)
        t = (np.arange(len(blocks))+.5)*width/sr
        axes[0].fill_between(t, blocks.min(axis=1), blocks.max(axis=1),
                             color=COLORS[c], alpha=.20, linewidth=.2, label=label(c))
    axes[0].set_ylabel('Left channel\namplitude')
    axes[0].legend(ncol=4, loc='upper right', fontsize=7)
    for ax, c in zip(axes[1:], candidates):
        f, t, Z = stft(audio[c][0][:, 0], fs=sr, window='hann', nperseg=2048,
                       noverlap=1536, boundary='zeros', padded=True)
        image = ax.pcolormesh(t, f/1000, 20*np.log10(np.maximum(np.abs(Z), 1e-7)),
                              vmin=-100, vmax=-20, cmap='magma', shading='auto', rasterized=True)
        ax.set_ylim(0, 8)
        ax.set_ylabel('kHz')
        ax.text(.01, .87, label(c), transform=ax.transAxes, color='white', fontsize=8)
    axes[-1].set_xlabel('Time from saved passage start (s)')
    axes[-1].set_xlim(0, len(audio['bypass'][0])/sr)
    fig.colorbar(image, ax=axes[1:], label='STFT magnitude (dB re 1 sample amplitude)', shrink=.75, pad=.015)
    fig.suptitle(label(name)+' · original-duration waveform and spectrum\n'
                 'Saved raw levels; common spectral scale; left channel shown', fontsize=11)
    save(fig, folder, name+'-waveform-spectrogram', generated)

    with np.load(root/'states'/(name+'.npz')) as data:
        t, features, regimes = data['time'], data['features'], data['states']
        fig, axes = plt.subplots(3, 1, figsize=(9.4, 7.4), sharex=True, layout='constrained')
        axes[0].stackplot(t, regimes.T, labels=REGIMES, colors=REGIME_COLORS, alpha=.9)
        axes[0].set_ylim(0, 1)
        axes[0].set_ylabel('Regime weight')
        axes[0].legend(ncol=6, loc='upper right', fontsize=7)
        for mode, depth in zip(MODES, (.16, .30, .30)):
            axes[1].plot(t, data[mode+'_governed']/depth, color=COLORS[mode+'_governed'],
                         label=f'{mode.capitalize()} / {depth:.2f}', linewidth=1.2)
        axes[1].plot(t, features[:, 5], color='#303846', linestyle=':', label='Confidence', linewidth=1.2)
        axes[1].set_ylabel('Fraction of ceiling\n/ confidence')
        axes[1].set_ylim(-.03, 1.08)
        axes[1].legend(ncol=4, loc='upper right', fontsize=7)
        axes[2].plot(t, features[:, 3], color='#087f8c', label='Input phase predictability C')
        axes[2].plot(t, features[:, 9]/np.pi, color='#b45b25',
                     label='Weighted prediction error / π', alpha=.8)
        axes[2].set_ylim(-1.05, 1.05)
        axes[2].set_ylabel('Phase proxies\n(dimensionless)')
        axes[2].set_xlabel('Frame-center label (s; whole frame is observed)')
        axes[2].legend(ncol=2, loc='lower right', fontsize=7)
        axes[2].set_xlim(0, len(audio['bypass'][0])/sr)
        fig.suptitle(label(name)+' · operational state and bounded controls\n'
                     'Regimes are overlapping engineering evidence, not identified piano notes', fontsize=11)
        save(fig, folder, name+'-state-controls', generated)


def phase_figure(rows, folder, generated):
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 6.6), layout='constrained')
    lookup = {(r['cell']['name'], r['candidate']): r['metrics'] for r in rows
              if r['cell']['sr'] == 48000 and r['cell']['channels'] == 2}
    for i, candidate in enumerate(COLORS):
        x = np.arange(len(SOURCES))+(i-1.5)*.19
        values = [lookup[(n, candidate)]['phase_prediction_abs_error_rad'] for n in SOURCES]
        axes[0].bar(x, values, width=.18, color=COLORS[candidate], label=label(candidate))
        values = [lookup[(n, candidate)].get('stereo_ipd_rms_rad', np.nan) for n in SOURCES]
        axes[1].bar(x, values, width=.18, color=COLORS[candidate])
    axes[0].set_ylabel('Prediction error (rad)')
    axes[0].legend(ncol=4, fontsize=7)
    axes[1].set_ylabel('Reanalysis IPD\nRMS change (rad)')
    axes[1].axhline(.10, color='#b13d35', linestyle='--', linewidth=1, label='Registered .10 rad screen')
    axes[1].legend(fontsize=7)
    for ax in axes:
        ax.set_xticks(np.arange(len(SOURCES)), [label(n).replace(' ', '\n', 1) for n in SOURCES], fontsize=8)
    fig.suptitle('Original-duration phase diagnostics · saved full-resolution measurements\n'
                 'Prediction consistency is a proxy; IPD is measured again after WOLA', fontsize=11)
    save(fig, folder, 'phase-comparison', generated)


def beat_figures(rows, source_manifest, folder, generated):
    cells = {(c['name'], c['sr'], c['channels']): c for c in source_manifest['cells']}
    for carrier in (440, 3520):
        fig, axes = plt.subplots(2, 2, figsize=(9.4, 7.4), layout='constrained')
        for candidate in COLORS:
            for damped in (False, True):
                selected = []
                for row in rows:
                    c = cells[(row['cell']['name'], row['cell']['sr'], row['cell']['channels'])]
                    if (row['candidate'] == candidate and c['kind'] == 'beating' and
                        c['base_hz'] == carrier and bool(c['tau_s']) == damped):
                        selected.append((c['delta_hz'], row['metrics']['beating']))
                selected.sort(key=lambda pair: pair[0])
                if not selected:
                    continue
                delta = [p[0] for p in selected]
                style = '--' if damped else '-'
                text = label(candidate)+(' · τ=6 s' if damped else ' · undamped')
                for ax, key in zip(axes.ravel(), ('spacing_error_hz', 'detrended_envelope_correlation',
                                                 'decay_relative_error', 'amplitude_modulation_relative_rms')):
                    value = [p[1].get(key) for p in selected]
                    if any(v is not None for v in value):
                        ax.plot(delta, [np.nan if v is None else v for v in value],
                                color=COLORS[candidate], linestyle=style, marker='o', markersize=3, label=text)
        d = np.array([.2, 1, 1.5, 3.])
        limit = np.maximum(.03, .03*d)
        axes[0, 0].plot(d, limit, color='#b13d35', linewidth=.8, alpha=.6)
        axes[0, 0].plot(d, -limit, color='#b13d35', linewidth=.8, alpha=.6)
        axes[0, 1].axhline(.98, color='#b13d35', linestyle=':', linewidth=1)
        axes[1, 0].axhline(.10, color='#b13d35', linestyle=':', linewidth=1)
        for ax, ylabel in zip(axes.ravel(), ('Fitted spacing error (Hz)', 'Detrended envelope correlation',
                                            'Relative decay-time error', 'Envelope modulation relative RMS')):
            ax.set_xlabel('True component separation Δf (Hz)')
            ax.set_ylabel(ylabel)
            ax.set_xticks(d)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='outside lower center', ncol=2, fontsize=7)
        fig.suptitle(f'{carrier} Hz beating references · original-duration fits\n'
                     'Solid: undamped; dashed: τ=6 s. Red: registered engineering limits.', fontsize=11)
        save(fig, folder, f'beat-comparison-{carrier}hz', generated)


def attack_figure(root, investigation_path, folder, generated):
    investigation = read_json(investigation_path)
    rows = investigation['results']
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 7.0), layout='constrained')
    historical = [max(abs(x) for x in r['historical_offsets_ms']) for r in rows]
    local = [max((abs(a['waveform_lag_ms']) for a in r['historical_reference_assessments']
                  if a['waveform_lag_ms'] is not None), default=np.nan) for r in rows]
    x = np.arange(len(rows))
    axes[0].bar(x-.18, historical, .35, color='#b45b25', label='Preserved Exp01 detector maximum shift')
    axes[0].bar(x+.18, local, .35, color='#087f8c', label='Independent local waveform lag maximum')
    axes[0].axhline(1, color='#b13d35', linestyle=':', linewidth=1)
    axes[0].set_ylabel('Absolute timing difference (ms)')
    axes[0].set_xticks(x, [f"{r['profile'].capitalize()} {r['amount']:.2f}\n{r['rate']/1000:g}k / {r['channels']}ch" for r in rows])
    axes[0].legend(fontsize=7)
    chosen, event = next(((r, a) for r in rows for a in r['historical_reference_assessments']
                          if a.get('peak_rank_flip')),
                         (rows[0], rows[0]['historical_reference_assessments'][0]))
    center = event['reference_seconds']
    for key, color, text, marker in [('original_slope_peaks', '#303846', 'Original production mode', 'o'),
                                     ('candidate_slope_peaks', '#b45b25', 'Preserved Exp01 candidate', 'x')]:
        peaks = event[key]
        xx = [(p['seconds']-center)*1000 for p in peaks]
        yy = [p['value'] for p in peaks]
        axes[1].scatter(xx, yy, color=color, marker=marker, label=text, s=32)
        axes[1].vlines(xx, 0, yy, color=color, alpha=.35, linewidth=1)
        for rank, (at, value) in enumerate(zip(xx, yy), 1):
            axes[1].annotate(str(rank), (at, value), xytext=(4, 3), textcoords='offset points', fontsize=7, color=color)
    axes[1].axvline(0, color='#303846', linestyle=':', linewidth=.8)
    axes[1].set_xlabel(f"Time from original-derived envelope-rise reference (ms; {chosen['rate']/1000:g} kHz)")
    axes[1].set_ylabel('Stored envelope-slope score\n(numbers indicate peak rank)')
    axes[1].legend(fontsize=7)
    fig.suptitle('Recorded-piano attack investigation · all six original failures retained\n'
                 'Zero waveform lag does not resolve detector disagreement or changed attack character', fontsize=11)
    save(fig, folder, 'attack-failure-investigation', generated)


def listening_documents(root, generated):
    key = read_json(root/'listening/BLIND_KEY.json')
    responses = root/'listening/RESPONSES.csv'
    if not responses.exists():
        with responses.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['trial', 'source', *QUESTIONS, 'notes', 'listener', 'session_date'])
            writer.writeheader()
            writer.writerows({'trial': row['trial'], 'source': row['source']} for row in key)
    with responses.open(newline='') as stream:
        answered = sum(any((row.get(q) or '').strip() for q in QUESTIONS) for row in csv.DictReader(stream))
    generated.append(responses)
    guide = Path(__file__).resolve().parents[2]/'docs/research/phase-governed-resonance-02/LISTENING_GUIDE.md'
    text = guide.read_text()
    if answered:
        text = text.replace('**Creator listening is pending.**', '**Creator response entries exist and remain uninterpreted.**')
    text += '\n## Blind original-duration trial index\n\n'
    text += 'The key is stored separately in `listening/BLIND_KEY.json`. Keep it closed until responses are recorded.\n\n'
    text += '| Trial | Source | A | B |\n| --- | --- | --- | --- |\n'
    for row in key:
        trial = row['trial']
        text += f"| {trial} | {label(row['source'])} | [A](listening/blind/{trial}/A.wav) | [B](listening/blind/{trial}/B.wav) |\n"
    supplement = read_json(root/'listening/MODE_DISTINCTNESS_KEY.json')
    text += '\n## Supplementary cross-mode distinctness trials\n\n'
    text += 'These 12 randomized pairs were prepared **after the primary freeze**, using the saved governed WAVs. '
    text += 'They directly compare Velvet/Legato, Velvet/Melt and Legato/Melt on each of the four original-duration sources. '
    text += 'One scalar RMS match and common 4× estimated-peak headroom gain are logged for each pair. '
    text += 'No DSP tuning or new primary evaluation is involved, and the original blind key is unchanged. '
    text += 'Outcomes remain pending. Use [the separate blank response sheet](listening/MODE_DISTINCTNESS_RESPONSES.csv) '
    text += 'and keep `listening/MODE_DISTINCTNESS_KEY.json` closed until responding.\n\n'
    text += '| Trial | Source | A | B |\n| --- | --- | --- | --- |\n'
    for row in supplement['trials']:
        text += f"| {row['trial']} | {label(row['source'])} | [A]({row['A_path']}) | [B]({row['B_path']}) |\n"
    slowed = read_json(root/'listening/SLOWDOWN_KEY.json')
    text += '\n## Supplementary matched slowed-piano trials — incomplete prototype\n\n'
    text += 'These 12 pairs were prepared **after the primary freeze**, using saved slowdown WAVs only: '
    text += 'two piano crops × 1.25×/1.50× expansion × three identities. Each pair compares the protected untreated stretch '
    text += 'with the same protected stretch followed by one governed identity. Scalar RMS matching and common '
    text += '4× estimated-peak headroom gains are logged in a separate key. '
    text += '**The underlying slowdown retains its frozen transient timing and smear failures.** '
    text += 'This independent-factor comparison neither clears those failures nor establishes original-duration improvement. '
    text += 'Creator outcomes remain pending. Use [the separate blank response sheet](listening/SLOWDOWN_RESPONSES.csv) '
    text += 'and keep `listening/SLOWDOWN_KEY.json` closed until responding.\n\n'
    text += '| Trial | Source | Expansion | A | B |\n| --- | --- | --- | --- | --- |\n'
    for row in slowed['trials']:
        text += f"| {row['trial']} | {label(row['source'])} | {row['ratio']:.2f}× | [A]({row['A_path']}) | [B]({row['B_path']}) |\n"
    text += '\n## Diagnostic figures\n\n'
    for path in generated:
        if path.suffix == '.png':
            relative = path.relative_to(root).as_posix()
            text += f'- [{label(path.stem)}]({relative}) ([vector SVG]({relative[:-4]}.svg))\n'
    text += '\n## Separate slowed prototypes\n\n'
    text += '**Transient gate incomplete:** these are exploratory files with known impulse timing/smear failures. '
    text += 'They are not part of the 40 original-duration blind trials and are not loudness-matched preference pairs.\n\n'
    slowdown = root/'slowdown/metrics.json'
    if slowdown.exists():
        records = read_json(slowdown)['records']
        text += '| Prototype | Audio |\n| --- | --- |\n'
        for row in records:
            text += f"| {row['path'][:-4]} | [WAV](slowdown/{row['path']}) |\n"
    else:
        text += 'Slowdown rendering has not been supplied to this presentation run.\n'
    text += '\nCreator responses are not interpreted or fabricated by this generator. Numerical change alone establishes no preference.\n'
    destination = root/'LISTENING_GUIDE.md'
    destination.write_text(text)
    generated.append(destination)
    return answered


def build(root, investigation_path=None):
    root = Path(root).resolve()
    for path in [root/'metrics.jsonl', root/'SUMMARY.json', root/'listening/BLIND_KEY.json',
                 *(root/'states'/(n+'.npz') for n in SOURCES)]:
        if not path.is_file():
            raise FileNotFoundError(f'Complete frozen evaluation required before presentation: {path}')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                         'axes.labelsize': 8, 'axes.titlesize': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.grid': False, 'svg.fonttype': 'none',
                         'svg.hashsalt': 'ISLA-Experiment-02', 'lines.linewidth': 1.0})
    folder = root/'figures'
    folder.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in (root/'metrics.jsonl').read_text().splitlines() if line]
    manifest = read_json(root/'SOURCE_MANIFEST.json')
    generated = []
    for source in SOURCES:
        passage_figures(root, folder, source, generated)
    phase_figure(rows, folder, generated)
    beat_figures(rows, manifest, folder, generated)
    if investigation_path is not None:
        attack_figure(root, investigation_path, folder, generated)
    generated.extend(make_mode_distinctness(root))
    generated.extend(make_slowdown_listening(root))
    answered = listening_documents(root, generated)
    guide_source = Path(__file__).resolve().parents[2]/'docs/research/phase-governed-resonance-02/LISTENING_GUIDE.md'
    inputs = [root/'metrics.jsonl', root/'SUMMARY.json', root/'SOURCE_MANIFEST.json',
              root/'listening/BLIND_KEY.json', guide_source,
              *(root/'states'/(n+'.npz') for n in SOURCES),
              *(root/'raw'/n/(c+'.wav') for n in SOURCES for c in COLORS)]
    if investigation_path is not None:
        inputs.append(Path(investigation_path))
    if (root/'slowdown/metrics.json').exists():
        inputs.append(root/'slowdown/metrics.json')
    freeze = read_json(root/'FREEZE.json') if (root/'FREEZE.json').exists() else None
    repo = Path(__file__).resolve().parents[2]
    generator_relative = Path(__file__).resolve().relative_to(repo).as_posix()
    frozen_generator = freeze is not None and generator_relative in freeze['code_and_protocol']
    result = {'role': 'Presentation-only secondary rendering of saved evidence; no DSP rerender and no new primary metric',
              'registration': 'Included in primary freeze' if frozen_generator else 'Generator and listening guidance added after the primary freeze; DSP and protocol remain frozen',
              'creator_listening': 'PENDING' if not answered else 'Existing responses present, not interpreted',
              'response_rows_with_entries': answered,
              'response_policy': 'Blank sheet initialized; existing responses never overwritten',
              'generator_sha256': digest(__file__),
              'generator_in_primary_freeze': frozen_generator,
              'primary_freeze_sha256': digest(root/'FREEZE.json') if freeze is not None else None,
              'input_sha256': {str(p): digest(p) for p in inputs},
              'output_sha256': {p.relative_to(root).as_posix(): digest(p) for p in generated}}
    (root/'PRESENTATION_MANIFEST.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'Created {len(generated)} figures/documents; no creator responses filled.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attack-investigation', type=Path)
    args = parser.parse_args()
    build(args.output, args.attack_investigation)
