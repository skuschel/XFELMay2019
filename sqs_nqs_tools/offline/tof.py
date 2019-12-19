import numpy as np
import matplotlib.pyplot as plt
import karabo_bridge as kb
import karabo_data as kd

from . import access
from .access import *
from . import adata as adata
from ..experimentDefaults import defaultConf


def averageTOF( tofs ): #check

    '''
    takes TOF data for a given run and averages.  
        inputs
            tofs = array of all tof data from a given run
        outputs
            an array of the averaged tof spectra  
    '''
    return np.mean( tofs, 0 )
    
def get_TOF_correction_for_multi_channel_sampling(data, bg=[0,defaultConf['tofBaseEnd']], samples=defaultConf['tofChannels'] ):
    '''
    takes a given tof trace (this can be also an average but does not have to be)
        inputs
            data = a single tof trace
            bg = a range considered as a baseline, by default from 0 to tofBaseEnd as specified in experiment Defaults
            samples = the number of TOF digitizer channels taken into consideration for correction default taken from experimentDefaults
        outputs
            a corrected tof trace  
    '''
    for idx in range(samples):
        data_idx_selection = np.arange(idx,len(data),samples)
        data_excerpt = data[data_idx_selection]
        if bg is not None:
            data_excerpt = data_excerpt - np.mean(data_excerpt[int(np.floor(bg[0]/samples)):int(np.floor(bg[1]/samples))])
        data[data_idx_selection] = data_excerpt
    return data

def plotTOF( pixels, tof, xlabel='pixels' ): 
    '''
    Plots TOF spectra, not callibrated for m/z 
        inputs 
            pixels = uncallibrated time of flight x-axis
            tof = array of a single TOF spectra
        outputs
            plot of tof data   
    '''
    plt.plot( pixels, tof )
    plt.ylim( np.max(tof), np.min(tof) )
    plt.xlabel( xlabel )
    plt.ylabel( 'TOF ' )
    plt.show()

def plotVerticalLine( xpos, scale = 1e6, color='k', label=None ):
    '''
    Plots vetical line that will be used to identify ROI
        inputs 
            xpos = position of vertical line 
        outputs
            plots vertical line
    '''
    if label is None:
        plt.plot( [xpos,xpos],np.array([-1,1])*scale, color )
    else:
        plt.plot( [xpos,xpos],np.array([-1,1])*scale, color, label=label )


def showROIs( pixels, tof, onePlus, lightPeak, highCharge ):
    '''
    used to overlay vertical  lines defining ROI's on TOF spectra
        inputs 
            pixels= uncallibrated time of flight x-axis
            tof = array of a single TOF spectra
            onePlus = array specificing range of TOF spectra considered for X+
            lightPeak = array specificing range of TOF spectra considered for light peak
            highCharge = array specificing range of TOF spectra considered for X(n+)
        outputs
            Plot of specified TOF spectra, with ROI's marked
    ''' 
    plt.figure( figsize=(10,5) )
    plotTOF(pixels , tof )

    onePlusLeft = onePlus[0]
    onePlusRight = onePlus[1]
    plotVerticalLine( onePlusLeft, color='g', label='1+' )
    plotVerticalLine( onePlusRight, color='g' )

    lightPeakLeft = lightPeak[0]
    lightPeakRight = lightPeak[1]
    plotVerticalLine( lightPeakLeft, color='r', label='Light peak' )
    plotVerticalLine( lightPeakRight, color='r' )

    highChargeLeft = highCharge[0]
    highChargeRight = highCharge[1]
    plotVerticalLine( highChargeLeft, color='k', label='High charge states' )
    plotVerticalLine( highChargeRight, color='k' )

    plt.legend(  ) 


def averageBrightestTOFs( pixels, tofs, integrateAt=(280000 - 1000,280000 + 1500), behlkeAt=268000 ): #check
    '''
    Averages the brightest TOFs from a given run, ie outlier rejection
        inputs 
            pixels = uncallibrated time of flight x-axis
            tofs = array of all tof data from a given run
        outputs
            a 1D array of the averaged brightest TOFs
    '''  
    fullSum = np.abs(np.sum( tofs[:,(behlkeAt<pixels)], 1 ))
    onePlusSum = np.nansum( tofs[:, (integrateAt[0]<pixels)&(pixels<integrateAt[1]) ], 1 )
    
    maxSum = np.max((fullSum))
    interestingShots = fullSum > maxSum*.5
    
    ratio = np.abs(onePlusSum.astype(float))[interestingShots]
    
    maxRatio = np.max(ratio)
    
    subtofs=tofs[interestingShots,:]
    return np.mean(subtofs[ratio > maxRatio*.8,:], 0)
    
      
def waterfallTOFs( pixels, tofs, labels=None, figsize=(10,5), waterfallDelta=None):  
    '''
    Plots all TOFs of a given run in a waterfall plot
        inputs 
            pixels= uncallibrated time of flight x-axis
            tofs=array of all tof data from a given run
        outputs
            waterfall plot, sans labels unless otherwise specified
    '''
    plt.figure(figsize=figsize)
    offset = 0.
    if labels is None:
        for tof in tofs:
            plt.plot( pixels , tof + offset )
            if waterfallDelta is None:
                offset += np.min( tof )
            else:
                offset += waterfallDelta
    else:
        startTextX = pixels[-1] - 2e3
        for tof, label in zip(tofs,labels):
            plt.plot( pixels , tof + offset, label=label )
            baseline = tof[0]+offset + 40        
            plt.annotate(label, (startTextX, baseline))
            if waterfallDelta is None:
                offset += np.min( tof )
            else:
                offset += waterfallDelta
        
        
def overlayTOFs( pixels, tofs, labels=None):  
    '''
    Plots all TOFs of a given run, overlayed 
        inputs 
            pixels= uncallibrated time of flight x-axis
            tofs=array of all tof data from a given run
        outputs
            plot of specified tof spectra, sans labels unless otherwise specified

    '''
    plt.figure(figsize=(10,5))
    if labels is None:
        for tof in tofs:
            plt.plot( pixels , tof, alpha=0.5 )
    else:
        for tof, label in zip(tofs,labels):
            plt.plot( pixels , tof, label=label, alpha=0.5 )
        plt.legend()

        
def generateFullCorrection( correction,  pixels, corrpixels ):
    maxPixel = np.max(pixels)
    minPixel = np.min(pixels)
    
    NTOF = correction.size
    
    fullCorrection = np.copy(correction)
    fullCorrpixels = np.copy(corrpixels)
    
    fcmin = np.min(fullCorrpixels)
    fcmax = np.max(fullCorrpixels)
    idx = 0
    while (fcmin >= minPixel)|(fcmax <= maxPixel):
        
        fullCorrpixels = np.concatenate((  corrpixels-NTOF*(idx+1.), fullCorrpixels, corrpixels+NTOF*(idx+1.)), axis=0)
        fullCorrection = np.concatenate((correction, fullCorrection , correction), axis=0)
        fcmin = np.min(fullCorrpixels)
        fcmax = np.max(fullCorrpixels)
        idx += 1
#         print(fcmin,fcmax)
        
    diffpixels = np.diff( fullCorrpixels )
    idx0 =  np.argmin(np.abs(pixels[0]-fullCorrpixels))
    idx1 =  np.argmin(np.abs(pixels[-1]-fullCorrpixels))
    
    return fullCorrection[idx0:idx1+1]

def correctTOF( tofs, pixels, correction, corrpixels ):
    fullCorrection = generateFullCorrection( correction, pixels, corrpixels )
    return tofs-fullCorrection 

def waterfallBrightest( pixels, tofs, nbright=100, 
                                      threshSum=0.1, behlkeAt=268000,
                                      integrateAt=(269000 - 200, 276000)):  
    '''
    Makes waterfall plot of the brightest TOF spectra from a given run, labeled with train ID
    Can be sorted by onePlus, lightPeak, or highCharge (defined at the top) by specifying onePlus =
        inputs
            pixels= uncallibrated time of flight x-axis
            tofs=array of all tof data from a given run
            trainIds = array of train IDs from a run
        displays
            waterfall plot
    '''
    plt.figure(figsize=(10,100))
    offset = 0.
    
    fullSum = np.abs(np.sum( tofs[:,(behlkeAt<pixels)], 1 ))
    
    maxSum = np.max((fullSum))
    interestingShots = fullSum > maxSum*threshSum
    
    onePlusSum = np.nansum( tofs[:, (integrateAt[0]<pixels)&(pixels<integrateAt[1]) ], 1 )
    
    ratio = np.abs(onePlusSum.astype(float) )[interestingShots]
    
    inds = np.argsort(ratio)[-nbright:]
    
    subtofs = tofs[interestingShots,:]
    
    for idx, currind in enumerate(inds):
        tof = subtofs[currind,:]
        plt.plot( pixels[behlkeAt<pixels] , tof[behlkeAt<pixels] + offset )
        offset += np.min( tof[behlkeAt<pixels] )
        
        
def waterfallBrightest_labelByTrainId( pixels, tofs, nbright=100, 
                                      threshSum=0.1, behlkeAt=268000,
                                      integrateAt=(269000 - 200, 276000),
                                      showplot = True):                             #check
    '''
    Makes waterfall plot of the brightest TOF spectra from a given run, labeled with train ID
    Can be sorted by onePlus, lightPeak, or highCharge (defined at the top) by specifying onePlus =
        inputs
            pixels= uncallibrated time of flight x-axis
            tofs=array of all tof data from a given run
            trainIds = array of train IDs from a run
        displays
            waterfall plot, w/ TIDs labeled
        outputs
            trainIDs of brightest shots
    '''
    plt.figure(figsize=(10,100))
    offset = 0.
    
    # integral over all values in tofrange that are larger than behlkeat
    fullSum = np.abs(np.sum( tofs[:,(behlkeAt<pixels)], 1 ))
    
    # maximum integral found
    maxSum = np.max((fullSum))
    
    # a shot is interesting when its integral is at least 10% of max reached value (for default thresSum=0.1)
    interestingShots = fullSum > maxSum*threshSum
    
    # integrate over integrateAt range for each spectrum
    onePlusSum = np.nansum( tofs[:, (integrateAt[0]<pixels)&(pixels<integrateAt[1]) ], 1 )
    
    # take abs value from integrals over integrateAt range  (to be able to look for highest value) and look only at interesting shots
    ratio = np.abs(onePlusSum.astype(float) )[interestingShots]
    
    # sort them by highest values and take the last `nbright` shots (eg 100)
    inds = np.argsort(ratio)[-nbright:]
    
    # no get the arrays with the interesting raw data from results
    subtofs = tofs[interestingShots,:]
    subtrains = np.asarray(tofs.trainId)
    
    startTextX = pixels[-1] - 2e3 #cosmetics
    
    #plot them all
    for idx, currind in enumerate(inds):
        tof = subtofs[currind,:]
        plt.plot( pixels[behlkeAt<pixels] , tof[behlkeAt<pixels] + offset )
        
        baseline = tof[0]+offset + 40
        
        
        plt.annotate(str( subtrains[ currind ] ), (startTextX, baseline))
        offset += np.min( tof[behlkeAt<pixels] )
    
    if showplot:
        plt.show()
    else:
        pass
        
    return subtrains[inds]

def getAvgRunsTOF( runRange, path, tofrange ):
    NR = runRange.size

    tofs=[]
    for ir,arun in enumerate(runRange):
        tids, tof, pixels  = adata.getTOF( arun, path=path, tofrange=tofrange)
        avgtof = averageTOF(tof)
        tofs.append(avgtof)
        
    return tofs

def getBrightAvgRunsTOF( runRange, path, tofrange, integrateAt =(280000 - 1000,280000 + 1500), behlkeAt=268000):
    NR = runRange.size

    tofs=[]
    for ir,arun in enumerate(runRange):
        tof, pixels = adata.getTOF( arun, path=path, tofrange=tofrange)
        avgtof = averageBrightestTOFs( pixels, tof, integrateAt=integrateAt, behlkeAt=behlkeAt )
        tofs.append(avgtof)
        
    return tofs


################ OLD TOF FUNCS #############33
def tofAverager( runData, nmax = 50 ):
    '''
    generates average of tofdata across nmax shots
    input:
        runData: run directory generated from karabo_data.RunDirectory(path+run)
        nmax: number of tof traces to average over from run
    output:
        averaged tof trace (np.array, float)
    '''
    tofsum = None
    isum = 0
    for tid, data in runData.trains():
    #     print("Processing train", tid)
        tofdata = data['SQS_DIGITIZER_UTC1/ADC/1:network']['digitizers.channel_1_A.raw.samples']
        if tofsum is None:
            tofsum = tofdata
            isum += 1
        else:
            tofsum += tofdata
            isum += 1
        if isum > nmax:
            break
    return tofsum/float(nmax)

def normalizedTOF( toftrace , downsampleRange=(268000,280000) , baselineFrom=-2000 ):
    '''
    input:
        toftrace: raw tof trace
        downsampleRange: (int,int) tuple giving range over which to downsmaple TOF
        baselineFrom: gives start index for calculating baseline average
    output:
        normalizedTOFTrace: puts tof trace in standard form for analysis
    '''
    # Reduce dimension of TOF to span desired range
    newtof = toftrace[downsampleRange[0]:downsampleRange[1]]
    N = newtof.size
    x = np.arange(N)

    # Substract mean of remaining TOF trace and take absolute value
    newtof_mean = np.mean( newtof[baselineFrom:] )
    return np.abs(newtof - newtof_mean)

from scipy.signal import find_peaks_cwt
def findTOFPeaks( toftrace ):
    '''
    input:
        toftrace: use normalized tof trace generated from normalizedTOF, numpy array of floats
    output:
        peak_positions: returns indexes of the TOF peaks
        peak_values: returns height of TOF peaks
    '''
    base_width = 200.
    # Find indexes of inds
    zf = find_peaks_cwt(toftrace, [base_width, base_width/2., base_width/4.])
    
    # Create averaging zones around peaks
    zguess = np.zeros_like(zf).astype(float) # allocate space

    for ii,zfi in enumerate(zf):
        xlow = (np.round( zfi - base_width/2. )).astype(int)
        if xlow < 0:
            xlow = 0
        xhigh = (np.round( zfi + base_width/2. )).astype(int)
        if xhigh > toftrace.size:
            xhigh = toftrace.size
            
        zguess[ii] = np.max(toftrace[xlow:xhigh])
        
    return zf, zguess


def tofROI( pixels, tofs, roi=(269000 - 200, 276000) ):
    return np.sum(np.array(tofs)[:,(roi[0]<pixels)&(pixels<roi[1])],1)



