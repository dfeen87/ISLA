# Original-signal estimator audit

**POST-FREEZE exploratory supplementary diagnostic. No estimator or threshold was retuned.**

Verified 30 source files and 40 frozen code/protocol files. This audit generated no candidate audio.

## Synthetic event comparison at 25 ms

|Source|Rate/channels|Detector|Events|Precision|Recall|Mean signed error ms|
|---|---|---|---|---|---|---|
|solo_piano|44100/1|Frozen core|4/4|1.000|1.000|-7.755|
|solo_piano|44100/1|librosa|4/4|1.000|1.000|12.562|
|connected_melody|44100/1|Frozen core|8/8|0.875|0.875|11.377|
|connected_melody|44100/1|librosa|8/8|1.000|1.000|17.834|
|percussion|44100/1|Frozen core|20/20|1.000|1.000|-7.891|
|percussion|44100/1|librosa|20/20|1.000|1.000|10.104|
|solo_piano|44100/2|Frozen core|4/4|1.000|1.000|-7.755|
|solo_piano|44100/2|librosa|4/4|1.000|1.000|12.562|
|connected_melody|44100/2|Frozen core|8/8|0.875|0.875|11.377|
|connected_melody|44100/2|librosa|8/8|1.000|1.000|17.834|
|percussion|44100/2|Frozen core|20/20|1.000|1.000|-7.891|
|percussion|44100/2|librosa|20/20|1.000|1.000|10.104|
|solo_piano|48000/1|Frozen core|4/4|1.000|1.000|-9.000|
|solo_piano|48000/1|librosa|4/4|1.000|1.000|12.333|
|connected_melody|48000/1|Frozen core|8/8|0.875|0.875|9.571|
|connected_melody|48000/1|librosa|8/8|1.000|1.000|17.333|
|percussion|48000/1|Frozen core|20/20|1.000|1.000|-7.133|
|percussion|48000/1|librosa|20/20|1.000|1.000|8.333|
|solo_piano|48000/2|Frozen core|4/4|1.000|1.000|-9.000|
|solo_piano|48000/2|librosa|4/4|1.000|1.000|12.333|
|connected_melody|48000/2|Frozen core|8/8|0.875|0.875|9.571|
|connected_melody|48000/2|librosa|8/8|1.000|1.000|17.333|
|percussion|48000/2|Frozen core|20/20|1.000|1.000|-7.133|
|percussion|48000/2|librosa|20/20|1.000|1.000|8.333|

Signed errors include matched events only; unmatched events are reported in the JSON. The 25 ms matching window is a detector-comparison convention, not an acceptable processing-delay tolerance. A perfect synthetic score would not establish physical strike detection on recordings.

## Recorded piano: detector agreement only

|Source|Rate/channels|Core/librosa counts|Matched within 25 ms|Core-minus-librosa mean ms|
|---|---|---|---|---|
|recorded_piano|44100/1|23/17|17|-19.805|
|recorded_piano_reserved|44100/1|21/18|18|-20.640|
|recorded_piano|44100/2|21/17|17|-19.805|
|recorded_piano_reserved|44100/2|20/17|17|-19.122|
|recorded_piano|48000/1|21/18|18|-16.593|
|recorded_piano_reserved|48000/1|28/19|19|-15.158|
|recorded_piano|48000/2|20/17|17|-15.686|
|recorded_piano_reserved|48000/2|24/17|17|-13.176|

No physical-strike annotation exists for these crops. Agreement and disagreement characterize detector behavior; neither detector is assumed to supply ground truth.

## Proxy limitations on original signals

|Source|Rate/channels|Median C|Median abs phase error rad|Median flatness|Attack-evidence peaks|
|---|---|---|---|---|---|
|percussion|44100/1|0.898968|0.291606|0.08910684|20|
|dense_mix|44100/1|0.946014|0.158682|0.00000108|30|
|simple_tone|44100/1|1.000000|0.000007|0.00000000|1|
|percussion|44100/2|0.898968|0.291809|0.08910685|20|
|dense_mix|44100/2|0.948396|0.154731|0.00000108|28|
|simple_tone|44100/2|1.000000|0.000007|0.00000000|1|
|percussion|48000/1|0.913814|0.270281|0.07446219|20|
|dense_mix|48000/1|0.949654|0.161666|0.00000080|34|
|simple_tone|48000/1|1.000000|0.000014|0.00000000|1|
|percussion|48000/2|0.913814|0.270279|0.07446219|20|
|dense_mix|48000/2|0.951530|0.159892|0.00000077|34|
|simple_tone|48000/2|1.000000|0.000014|0.00000000|1|
|beat_440_0.2_steady|48000/1|1.000000|0.000015|0.00000000|6|
|beat_440_0.2_damped|48000/1|1.000000|0.000015|0.00000000|6|

Each 0.2 Hz beating fixture has one registered excitation yet produces six attack-evidence peaks: the initial excitation, four interior peaks near 2.635, 7.637, 12.640 and 17.643 s following beat minima, and an ending-related peak at 20.117 s (the source cuts off at 20.125 s). The interior events show that changes from beating can activate the frozen detector; the ending is a separate boundary artifact. High C and low flatness do not resolve that ambiguity. Percussion also has median C near 0.9 and a high 1-flatness score, so those proxies are not exclusive to stable pitched sustain.

These proxies describe spectral structure and predictable bin-phase motion. They do not identify real note stages. Full non-silent and reliable-subset distributions, counts and source hashes are in ESTIMATOR_AUDIT.json.

## Definitions and references

- **status:** POST-FREEZE exploratory supplementary diagnostic; original signals only; no frozen estimator/threshold changed
- **our_detector:** Frozen core.analyze feature6 (attack evidence, not normalized attack regime weight); scipy.signal.find_peaks height>=0.5, distance=ceil(0.050*sr/512) frames. Plateau peaks use scipy's middle sample. Only core frame-center times in [0,input duration) are retained; no empirical time correction.
- **core_frame_times:** (frame_index*hop-frame+hop+frame/2)/sr, exactly the frozen core time vector. N=2048/H=512 frames include complete offline support; timestamps are analysis frame centers, not physical strike claims.
- **reference_strength:** librosa 1.0.0 onset_strength: N=2048/H=512, lag=1, max_size=1 (frequency max filtering disabled), detrend=False, center=True; default log-power Mel feature and mean frequency aggregation. Compute per-channel envelopes then average channel envelopes; never waveform-downmix stereo.
- **reference_picking:** librosa.onset.onset_detect on that envelope: normalize=True, backtrack=False, sparse=True, units=time; explicit installed defaults pre_max=floor(0.03*sr/H), post_max=1, pre_avg=floor(0.10*sr/H), post_avg=floor(0.10*sr/H)+1, wait=floor(0.03*sr/H), delta=0.07. Library frame times are index*H/sr with its documented centered-strength compensation; no added N/2 offset.
- **matching:** One-to-one maximum-cardinality matches with absolute timing difference<=25 ms; minimize total absolute error among those matches. Unmatched detections are false positives only for synthetic ground truth; unmatched known synthetic events are false negatives. Precision=matches/detections; recall=matches/events. Empty denominator gives null. Signed error=detected-reference, so positive means later.
- **recorded_scope:** The two crops have no physical hammer-strike ground truth. Report only counts and one-to-one detector agreement within 25 ms; reference-matched fractions are agreement, never precision/recall accuracy. No listening or note-stage identification is inferred.
- **proxy_frames:** Descriptive medians and 10th/90th percentiles on frozen non-silent frames (feature8==0), also subset with any frozen reliable bin. Features: C=3, phase prediction weighted absolute error radians=9, flatness=1-feature2, confidence=5. Reliability is frozen core's current/previous magnitude gate, not a three-frame proof.
- **proxy_limits:** Flatness is an inexpensive spectral-structure proxy, not stable pitch or harmonic correctness. C is bin-phase predictability, not musical-state truth. A high tonal score or C on percussion/close beating does not validate note labels. Reused synthetic cells/formats are correlated observations, not independent recordings.
- **scope:** All 4 sample-rate/channel formats for solo_piano, connected_melody, percussion and each recorded crop; proxy stats additionally simple_tone/dense_mix all 4 and 0.2 Hz beating steady/damped 48 kHz mono. No candidate signal was generated or rerendered.
- **reference_version_note:** Official 0.11.0 API pages are the references already cited in frozen UFO_PRIOR_ART.md and were checked for these documented semantics. Execution uses installed 1.0.0; the installed onset module source file is hash recorded. This is the default spectral-flux comparator, not the max-filtered SuperFlux configuration.

The official [onset-strength reference](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_strength.html) documents the log-Mel spectral-flux default and max_size=1 disabling frequency max filtering. The official [onset-detection reference](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_detect.html) documents normalized peak picking and optional backtracking. These are the same primary API sources cited in the frozen U.F.O./DSP prior-art report; execution is pinned to installed librosa 1.0.0 and its onset-module hash.
