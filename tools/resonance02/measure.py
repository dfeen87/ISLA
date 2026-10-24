"""Auditable numerical proxies. None of these establishes audible improvement."""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import resample_poly, hilbert
from scipy.optimize import least_squares, minimize_scalar
from tools.resonance02.core import Config, stft, principal
from tools.resonance02.attacks import assess_attacks

def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype=float)**2)))
def peak(x):return float(np.max(np.abs(x))) if np.size(x) else 0.
def db(a,b):return float(20*np.log10(a/b)) if min(a,b)>1e-14 else None
def envelope(x,sr):return np.sqrt(np.maximum(uniform_filter1d(np.mean(x*x,axis=1),max(1,round(.001*sr)),mode='constant'),0))

def tone_frequency(x,sr,expected):
    y=np.mean(x[round(.3*sr):-round(.3*sr)],axis=1)
    if len(y)<4 or rms(y)<1e-12:return None
    n=2**int(np.ceil(np.log2(len(y)*4)))
    S=np.abs(np.fft.rfft(y*np.hanning(len(y)),n=n));f=np.fft.rfftfreq(n,1/sr)
    band=np.flatnonzero(abs(f-expected)<5)
    i=int(band[np.argmax(S[band])]);l=np.log(S[i-1:i+2]+1e-30)
    offset=.5*(l[0]-l[2])/(l[0]-2*l[1]+l[2])
    return float((i+offset)*sr/n)

def beat_metrics(x,y,sr,cell):
    if sr not in (44100,48000) or min(rms(x),rms(y))<1e-12:
        raise ValueError('Unmeasurable beating input or unsupported sample rate')
    base,delta=cell['base_hz'],cell['delta_hz'];tau=cell['tau_s']
    # Heterodyne then anti-aliased decimation: independently fit two frequencies.
    t=np.arange(len(y))/sr-.125
    demod=resample_poly(y[:,0]*np.exp(-2j*np.pi*base*t),1,sr//100)
    tsmall=np.arange(len(demod))/100-.125
    keep=(tsmall>.2)&(tsmall<19.8);tt=tsmall[keep];observed=demod[keep]
    def fitfun(params,return_coeff=False):
        offset,sep,decay=params
        B=np.exp(-decay*tt[:,None])*np.exp(2j*np.pi*tt[:,None]*np.array([offset,offset+sep]))
        coeff=np.linalg.lstsq(B,observed,rcond=None)[0];res=B@coeff-observed
        return coeff if return_coeff else np.r_[res.real,res.imag]
    fit=least_squares(fitfun,[0,delta,1/tau if tau else 0],
                      bounds=([-.2,max(.02,delta-.2),-.05],[.2,delta+.2,1.]),
                      max_nfev=35,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    offset,spacing,decay=fit.x
    # Hilbert amplitude at long-record interior; de-damp only for beat statistics.
    sl=slice(round(.325*sr),round(19.925*sr))
    a=np.abs(hilbert(x[:,0]))[sl][::240];b=np.abs(hilbert(y[:,0]))[sl][::240]
    interior=t[sl][::240]
    if tau:a=a*np.exp(interior/tau);b=b*np.exp(interior/tau)
    cor=float(np.corrcoef(a,b)[0,1])
    # Frequency of the amplitude-squared cycle estimated independently from curve fit.
    power=b*b
    def cost(hz):
        B=np.c_[np.ones(len(interior)),np.cos(2*np.pi*hz*interior),np.sin(2*np.pi*hz*interior)]
        return float(np.mean((B@np.linalg.lstsq(B,power,rcond=None)[0]-power)**2))
    # Coarse scan avoids a local side-lobe minimum on long records.
    grid=np.linspace(max(.02,delta-.15),delta+.15,61);best=grid[np.argmin([cost(f) for f in grid])]
    result=minimize_scalar(cost,bounds=(max(.02,best-.006),best+.006),method='bounded')
    tau_fit=float(1/decay) if decay>1e-8 else None
    return dict(two_tone_spacing_hz=float(spacing),spacing_error_hz=float(spacing-delta),
                carrier_offset_hz=float(offset),fit_residual_rms=float(np.sqrt(np.mean(fit.fun**2))),
                beat_envelope_frequency_hz=float(result.x),beat_frequency_error_hz=float(result.x-delta),
                detrended_envelope_correlation=cor,amplitude_modulation_relative_rms=rms(b-a)/max(rms(a),1e-14),
                fitted_tau_s=tau_fit,decay_relative_error=abs(tau_fit/tau-1) if tau and tau_fit else None,
                fitted_decay_rate_per_s=float(decay))

def reference(x,sr,cell):
    S,_,_=stft(x)
    return dict(X=S,env=envelope(x,sr),rms=rms(x),cell=cell)

def metrics(x,y,sr,cell,ref):
    if x.shape!=y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Invalid output rejected before numerical measurement')
    S,_,_=stft(y);A=np.abs(S);B=np.abs(ref['X'])
    reliable=(B>np.max(B,axis=-1,keepdims=True)*1e-3)&(B>1e-7)
    q=B*B*reliable
    spectral=float(np.sqrt(np.sum(q*(np.log(np.maximum(A,1e-10))-np.log(np.maximum(B,1e-10)))**2)/max(q.sum(),1e-20)))
    ey=envelope(y,sr);ex=ref['env'];events=cell['events_seconds']
    select=np.zeros(len(x),dtype=bool)
    for t in events:select[max(0,round((t-.1)*sr)):min(len(x),round((t+.15)*sr))]=True
    rough_y,rough_x=rms(np.diff(ey)),rms(np.diff(ex))
    if select.any():
        rough_y=rms(np.diff(ey)[select[:-1]]);rough_x=rms(np.diff(ex)[select[:-1]])
    attacks=assess_attacks(x,y,sr,None if cell['kind']=='recorded' else events[:12]) if (events or cell['kind']=='recorded') else []
    omega=2*np.pi*np.arange(S.shape[-1])/2048
    residual=principal(np.diff(np.angle(S),axis=0)-omega[None,None,:]*512)
    pred=principal(np.diff(np.angle(S),axis=0)[1:]-512*(omega[None,None,:]+residual[:-1]/512))
    qphase=q[2:]*reliable[1:-1]*(A[2:]>1e-7)*(A[1:-1]>1e-7)
    parseval=np.full(A.shape[-1],2.);parseval[[0,-1]]=1.
    m=dict(finite=bool(np.isfinite(y).all()),same_length=len(x)==len(y),sample_peak=peak(y),
           oversampled_4x_peak=peak(resample_poly(y,4,1,axis=0)),
           rms_gain_db=float(20*np.log10(max(rms(y),1e-20)/ref['rms'])) if ref['rms']>1e-20 else None,
           relative_waveform_rms=rms(y-x)/max(ref['rms'],1e-20),
           spectral_log_envelope_rms=spectral,
           envelope_roughness_ratio=rough_y/rough_x if rough_x>1e-14 else None,
           envelope_roughness_scope='original-event windows' if select.any() else 'whole passage',
           phase_prediction_abs_error_rad=float(np.sum(qphase*np.abs(pred))/max(qphase.sum(),1e-20)),
           max_frame_energy_ratio=float(np.max(np.sum(A*A*parseval,axis=(1,2))/np.maximum(np.sum(B*B*parseval,axis=(1,2)),1e-20))),
           settled_tail_peak=peak(y[-round(.025*sr):]),attacks=attacks,
           attack_max_lag_ms=max((abs(r['waveform_lag_ms']) for r in attacks if r['waveform_lag_ms'] is not None),default=None),
           attack_unresolved_count=sum(bool(r['unresolved']) for r in attacks))
    if y.shape[1]==2:
        weight=np.sqrt(B[:,0]*B[:,1])*reliable[:,0]*reliable[:,1]*(A[:,0]>1e-7)*(A[:,1]>1e-7)
        ipd=principal(np.angle(S[:,0]*np.conj(S[:,1]))-np.angle(ref['X'][:,0]*np.conj(ref['X'][:,1])))
        m['stereo_ipd_rms_rad']=float(np.sqrt(np.sum(weight*ipd*ipd)/max(weight.sum(),1e-20)))
        before,after=db(rms(x[:,0]),rms(x[:,1])),db(rms(y[:,0]),rms(y[:,1]))
        m['balance_delta_db']=after-before if before is not None and after is not None else None
        correlations_defined=np.all(np.std(x,axis=0)>1e-12) and np.all(np.std(y,axis=0)>1e-12)
        m['stereo_correlation_delta']=float(np.corrcoef(y.T)[0,1]-np.corrcoef(x.T)[0,1]) if correlations_defined else None
    if cell['name']=='simple_tone':
        f=tone_frequency(y,sr,440);fx=tone_frequency(x,sr,440)
        m['pitch_delta_cents']=float(1200*np.log2(f/fx)) if f and fx else None
    if cell['name']=='gapped_tone':m['gap_center_peak']=peak(y[round(2.2*sr):round(2.3*sr)])
    if cell['kind']=='beating':m['beating']=beat_metrics(x,y,sr,cell)
    failures=[];flags=[]
    if not m['finite'] or not m['same_length']:failures.append('invalid_output')
    if max(m['sample_peak'],m['oversampled_4x_peak'])>=.98:failures.append('peak')
    if m['rms_gain_db'] is not None and abs(m['rms_gain_db'])>2:failures.append('rms_gain')
    if m['settled_tail_peak']>1e-10:failures.append('settled_silence')
    if m.get('gap_center_peak',0)>1e-10:failures.append('gap_silence')
    if abs(m.get('pitch_delta_cents') or 0)>3:failures.append('pitch')
    if cell['name']=='simple_tone' and m.get('pitch_delta_cents') is None:failures.append('pitch_unmeasurable')
    if m.get('stereo_ipd_rms_rad',0)>.1:failures.append('stereo_ipd')
    if abs(m.get('balance_delta_db') or 0)>.5:failures.append('stereo_balance')
    for row in attacks:
        if row['waveform_lag_ms'] is not None and abs(row['waveform_lag_ms'])>1 and (row['waveform_ncc']['maximum'] or 0)>=.8:failures.append('waveform_attack_timing')
        if abs(row.get('first_10ms_energy_gain_db') or 0)>2:failures.append('attack_energy')
        if row['unresolved']:flags.append('attack_detector_or_character_unresolved')
    if 'beating' in m:
        b=m['beating'];tol=max(.03,.03*cell['delta_hz'])
        if max(abs(b['spacing_error_hz']),abs(b['beat_frequency_error_hz']))>tol:failures.append('beating_frequency')
        if b['detrended_envelope_correlation']<.98:failures.append('beating_envelope')
        if b['decay_relative_error'] is not None and b['decay_relative_error']>.1:failures.append('decay')
    m['screen_failures']=sorted(set(failures));m['unresolved_flags']=sorted(set(flags))
    return m
