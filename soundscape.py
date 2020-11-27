import numpy as np
from scipy import signal
from scipy.interpolate import interp1d
from scipy.fftpack import next_fast_len

def spectrogram(data, windowSize=512, overlap=None, fs=48000, windowType='hanning', normalized=False, logf=False):
    """
    Computes the spectrogram and the analytic envelope of the signal
    """
    #force to power of next fast FFT length
    windowSize = next_fast_len(windowSize)
    if overlap is None:
        overlap = windowSize//8
    if data.ndim == 1:
        data = data[:,np.newaxis] # el array debe ser 2D
    nsamples, nchan = np.shape(data)
    nt = int(np.floor((nsamples-windowSize)/(windowSize-overlap)))+1
    nenv = next_fast_len(nsamples)
    # Dict for spectrogram
    listofkeys = ['nchan','f','t','s','env','nt','nf','df','window','type','overlap','log']
    spec = dict.fromkeys(listofkeys,0 )
    spec['nchan'] = nchan
    spec['nf'] = windowSize//2+1
    spec['s'] = np.zeros((nchan,spec['nf'],nt))
    spec['env'] = np.zeros((nchan,nenv))
    spec['window'] = windowSize
    spec['type'] = windowType
    spec['overlap'] = overlap
    spec['logf'] = logf
    spec['nt'] = nt
    for n in np.arange(nchan):
        env = np.abs(signal.hilbert(data[:,n],nenv))  
        f,t,spectro = signal.spectrogram(data[:,n], fs, window=windowType, nperseg=windowSize, noverlap=overlap)
        spec['t'] = t
        spec['df'] = f[1]
        spec['env'][n] = env
        if logf:
            lf = np.power(2,np.linspace(np.log2(f[1]),np.log2(f[-1]),spec['nf']))
            fint = interp1d(f,spectro.T,fill_value="extrapolate")
            spec['f'] = lf
            spec['s'][n] = fint(lf).T
        else:
            spec['f'] = f
            spec['s'][n] = spectro
        if normalized:
            spec['s'][n] = spec['s']/np.max(spec['s'][n])
            spec['env'][n] = spec['env']/np.max(spec['env'][n])    
    return spec        

def subspecs(spec,tstep,overlap=0.5):
    """
    Creates subspectrograms and subenvelopes from spec of window size tstep/(1-overlap) with time step tstep
    """
    twin = int(np.around(tstep/(1-overlap)))
    ts = np.arange(0,spec['nt']-twin,tstep)
    subs = np.array([spec['s'][:,:,t0:t0+twin] for t0 in ts])
    subenv = np.array([spec['env'][:,t0:t0+twin] for t0 in ts])
    ts += twin//2    
    return subs.swapaxes(0,1),subenv.swapaxes(0,1),spec['t'][ts]

    
def gini(values,ax=0):
    """
    Compute the Gini index of values.
    """
    values.sort(axis=ax)
    n = values.shape[ax]
    idx = np.arange(1, n+1).reshape(-1,1)*np.ones_like(values)
    G = np.sum(values*idx,axis=ax)
    G = 2*G/np.sum(values,axis=ax) - (n+1)
    return G/n

def indices(spec,tstep,**kwargs):
    """
    Compute ALL indices
    """
    listofkeys = ['nchan','t','aci','bi','ndsi','aei','adi','hs','ht','sc','db']
    ind = dict.fromkeys(listofkeys,0)
    subspec,subenv,t = subspecs(spec,tstep)
    ind['t']=t
    ind['nchan']=spec['nchan']
    pars = kwargs['Parameters']
    spec_norm = subspec/np.amax(subspec,axis=(-2,-1))[...,np.newaxis,np.newaxis]
    ind['sc'] = np.sum(subspec*spec['f'][...,np.newaxis],axis=(-2,-1))/np.sum(subspec,axis=(-2,-1))
    ind['db'] = 20*np.log10(np.mean(subenv,axis=-1))
    if 'ACI' in pars:
        ind['aci'] = np.sum(np.sum(np.diff(subspec),axis=-1)/np.sum(subspec[0],axis=-1),axis=-1)
    if 'BI' in pars:
        f_bin = [int(np.around(a/spec['df'])) for a in kwargs['freq_BI']]
        spec_mean = 10*np.log10(np.mean(np.square(spec_norm), axis=-1))
        spec_mean_segment =  spec_mean[...,f_bin[0]:f_bin[1]]
        spec_mean_segment_norm = spec_mean_segment - np.min(spec_mean_segment)
        ind['bi'] = np.sum(spec_mean_segment_norm/spec['df'],axis=-1) 
    if 'NDSI' in pars:
        anthro_bin = [int(np.around(a/spec['df'])) for a in kwargs['freq_anthro']]
        bio_bin = [int(np.around(a/spec['df'])) for a in kwargs['freq_bio']]
        anthro = np.sum(subspec[:,:,anthro_bin[0]:anthro_bin[1],:],axis=(-2,-1))
        bio = np.sum(subspec[:,:,bio_bin[0]:bio_bin[1],:],axis=(-2,-1))
        ind['ndsi'] = (bio-anthro)/(bio+anthro)
    if 'HS' in pars:
        spec_av =  np.sum(subspec,axis=-1)
        spec_av /= np.sum(spec_av,axis=-1)[...,np.newaxis]
        ind['hs'] = -np.sum(spec_av*np.log2(spec_av),axis=-1)/np.log2(spec['nf']) 
    if 'HT' in pars:
        subenv[subenv<kwargs['tol']]=kwargs['tol']
        ind['ht'] = -np.sum(subenv*np.log2(subenv),axis=-1)/np.log2(subenv.shape[-1])
    if 'AEI' in pars or 'ADI' in pars:
        bands_Hz = range(0, kwargs['max_freq'], kwargs['freq_step'])
        bands_bin = [int(np.around(f / spec['df'])) for f in bands_Hz]
        spec_AEI = 20*np.log10(spec_norm)
        spec_AEI_bands = np.array([spec_AEI[:,:,bb:bb+bands_bin[1],:] for bb in bands_bin])
        val = np.average(spec_AEI_bands>kwargs['db_threshold'],axis=(-2,-1)).swapaxes(0,1)
        if 'AEI' in pars:
            ind['aei']=gini(val,ax=1)
        if 'ADI' in pars:
            val[val<kwargs['tol']]=kwargs['tol']
            ind['adi'] = np.sum(-val/np.sum(val,axis=(0,1))*np.log(val/np.sum(val,axis=(0,1))),axis=1)
    return ind





