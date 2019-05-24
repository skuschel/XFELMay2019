#!/usr/bin/env python3

# quick and ditry script to just show hits
# based on work by Stephan Kuschel, Matt Ware, Catherine Saladrigas, Christian Peltz 2019

import numpy as np
import pyqtgraph as pg
import sqs_nqs_tools.online as online
import sqs_nqs_tools as tools
from pyqtgraph.ptime import time

#@xfel.filter
#def filterbywhatever(ds, thres=5):
#    '''
#    Place holder for outlier rejection
#    '''
#    if whatever(d) < thres:
#        return True


def plotHits(d):
    '''
    Plots current time of flight data from one shot.
    Updates _tofplot window
    Input:
        image data
    Output:
        None, updates plot window
    '''
    hitBuffer(d['image']) #add the image to the hit buffer
    tofBuffer(d['tof']) #add the tof to the hit buffer
    bestIm(d['image'], np.sum(d['image'])) #add tat the best hit
    
    hitsFig.plotImBuffer(hitBuffer) #plot up the hits
    tofFig.plotTofBuffer(tofBuffer) #plot up the hits
    
    bestFig.plotImBuffer(bestIm) #plot up the high scores
    
    pg.QtGui.QApplication.processEvents() #make sure it displays
 #  print('Photon flux = ', d['phoFlux'])
    return d
#plotHits = online.pipeline_parallel(1)(_plotHits) #if it is to be a pipeline

#1. setup some plots and buffers
imBufferLength = 4
hitBuffer = tools.DataBuffer(imBufferLength) #a buffer to store hits in
tofBuffer = tools.DataBuffer(imBufferLength) #a buffer to store hits in 

bestIm = tools.SortedBuffer(imBufferLength) #a buffer to store the brightest 

hitsFig = online.ImBufferPlotter(imBufferLength)
tofFig = online.TofBufferPlotter(imBufferLength)
bestFig = online.ImBufferPlotter(imBufferLength)
#imageViews, imFig = online.makeImageBufferPlots(imBufferLength) #a figure to show that buffer in

def main(source):
    '''
    Iterate over the datastream served by source
    Input:
        source: ip address as string
    Output:
        none, updates plots
    '''
       
    ds = online.servedata(source) #get the datastream
    ds = online.getImageandTof(ds) #get the tofs and images from it
    
    #get a random piece of data
    ds = online.getSomeDetector(ds, name='phoFlux', spec0='SA3_XTD10_XGM/XGM/DOOCS', spec1='pulseEnergy.photonFlux.value')
        
    #3. filter the data for hits
    #TODO
    
    #4. display latest n images and tofs in ring buffer
    for data in ds: #this could be made into a pipeline maybe
        plotHits(data)
    
    #ds is the datastream - everything is done in pipeline form


if __name__=='__main__':
	#parse args and fire main
    main(online.parseSource())






