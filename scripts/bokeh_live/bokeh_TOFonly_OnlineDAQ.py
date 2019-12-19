# IMPORT MODULES
import time
import numpy as np
import pandas as pd
import holoviews as hv
import datashader as ds
from holoviews.operation.datashader import datashade, rasterize
from holoviews.operation import decimate

from holoviews import opts
from holoviews.streams import Pipe, RangeXY, PlotSize, Buffer
import holoviews.plotting.bokeh
from tornado import gen
import tornado
from scipy.misc import imresize
from scipy import signal

from bokeh.plotting import figure, curdoc
from bokeh.layouts import column, row
from bokeh.document import without_document_lock
from bokeh.models.widgets import Button, Paragraph, Div
from functools import partial

from threading import Thread

import sqs_nqs_tools.online as online
import sqs_nqs_tools as tools

# MODULE CONFIGS
hv.extension('bokeh')
renderer = hv.renderer('bokeh')  # renderer to convert objects from holoviews to bokeh
renderer = renderer.instance(mode="server")
hv.output(dpi=300, size=100)
doc = curdoc()  # DOC for Bokeh Objects

# DATA SOURCE
source = 'tcp://10.253.0.142:6666'  # LIVE
#source = 'tcp://127.0.0.1:8011' # emulated live
tof_in_stream = True
pnCCD_in_stream = True
gmd_in_stream = False
tof_area_integrals = True
use_tof_cal_axis = False

img_downscale = 15

makeBigData_stop = False
# DATA CONFIG
N_datapts = 40000 # total number of TOF datapoints that are visualized
start_tof = 50000 # index of first TOF datapoint considered
xlim_tof = (start_tof,start_tof+N_datapts)
if use_tof_cal_axis:
    xlim_tof = (1,200)
## yielded config values
end_tof = start_tof+N_datapts # index of last TOF datapoint considered
x_tof = np.arange(start_tof,end_tof) # x-axis for tof data points

integral_range_1 = [63000,63700]
integral_range_2 = [63700,64600]
integral_range_3 = [70000,74000]

# Data handling functions
@gen.coroutine
def update_pipe(x,y,pipe):
    pipe.send((x,y))

@online.pipeline
def processTofs(d):
    '''
    process tofs in pipeline
    '''
    #d['tof'] = d['tof'][start_tof:end_tof] # cut out index range that we are interested in
    d['x_tof'] = x_tof # add values for x axis
    d['x_tof_cal'] = d['x_tof']
    # do tof multi channel correction
    if True:
        data = d['tof'] 
        samples = 16
        bg=[0,5000]
        for idx in range(samples):
            data_idx_selection = np.arange(idx,N_datapts,samples)
            data_excerpt = data[data_idx_selection]
            if bg is not None:
                data_excerpt = data_excerpt - np.mean(data_excerpt[int(np.floor(bg[0]/samples)):int(np.floor(bg[1]/samples))])
            data[data_idx_selection] = data_excerpt
        d['tof'] = data
    if True: # xaxis calibration
        d['x_tof_cal'] = 1/ (2.64e-4+1.1461e-9*(d['x_tof']-5.8146443e4)**2)
    return d

class performanceMonitor():
    def __init__(self,trainStep=1):
        import time
        self.t_start = time.time()
        self.t_start_loop = self.t_start
        self.for_loop_step_dur = 0
        self.n=-1
        self.freq_avg = 0
        self.dt_avg = 0
        self.trainId = 0
        self.trainId_old = -1
        self.skip_count = 0
        self.trainStep = trainStep

    def iteration(self):
        self.n+=1
        self.dt = (time.time()-self.t_start)
        self.t_start = time.time()
        freq = 1/self.dt
        if self.n>0:
            self.dt_avg = (self.dt_avg * (self.n-1) + self.dt) / self.n
            freq_avg = 1/self.dt_avg
            loop_classification_percent = self.for_loop_step_dur/0.1*100
            if loop_classification_percent < 100:
                loop_classification_msg="OK"
            else:
                loop_classification_msg="TOO LONG!!!"
            print("Frequency: "+str(round(freq_avg,1)) +" Hz  |  skipped: "+str(self.skip_count)+" ( "+str(round(self.skip_count/self.n*100,1))+" %)  |  n: "+str(self.n)+"/"+str(self.trainId)+"  |  Loop benchmark: "+str(round(loop_classification_percent,1))+ " % (OK if <100%) - "+loop_classification_msg)
        self.t_start_loop = time.time()

    def update_trainId(self,tid):
        self.trainId_old = self.trainId
        self.trainId = tid
        if self.n == 0:
            self.trainId_old = str(int(tid) -1)
        if int(self.trainId) - int(self.trainId_old) is not self.trainStep:
            self.skip_count +=1

    def time_for_loop_step(self):
        self.for_loop_step_dur = time.time()-self.t_start_loop

def get_TOF_correction_for_multi_channel_sampling(data, bg=[0,5000], samples=16 ):
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

def makeDatastreamPipeline(source):
    ds = online.servedata(source) #get the datastream
    ds = online.getTof(ds,idx_range=[start_tof,end_tof]) #get the tofs
    ds = processTofs(ds) #treat the tofs
    ds = online.getSomeDetector(ds, name='tid', spec0=defaultConf['tofDevice'], spec1='digitizers.trainId') #get current trainids from digitizer property
    #ds = online.getSomeDetector(ds, name='tid', spec0='SA3_XTD10_XGM/XGM/DOOCS:output', spec1='timestamp.tid', readFromMeta=True) #get current trainids from gmd property
    #if pnCCD_in_stream:
        #ds = online.getSomePnCCD(ds, name='pnCCD', spec0='SQS_NQS_PNCCD1MP/CAL/CORR_CM:output', spec1='data.image') #get pnCCD
        #ds = online.getSomeDetector(ds, name='tid', spec0='SQS_NQS_PNCCD1MP/CAL/PNCCD_FMT-0:output', spec1='timestamp.tid', readFromMeta=True) #get current trainids from gmd property

    #ds = online.getSomeDetector(ds, name='gmd', spec0='SA3_XTD10_XGM/XGM/DOOCS:output', spec1='data.intensitySa3TD') #get GMD
    return ds

def makeBigData():
    print("Source: "+ source) # print source set for data

    # Setup Data Stream Pipeline
    ds = makeDatastreamPipeline(source)

    perf = performanceMonitor() # outputs to console info on performance - eg what fraction of data was not pulled from live stream and thus missed
    #print
    n=-1
    print("Start Live Display")
    for data in ds:
        n+=1
        perf.iteration()
        if True:
            # performance monitor - frequency of displaying data + loop duration
            

            # Hand Data from datastream to plots and performance monitor

            # Thinga for data buffers
            ## TOF integral
            if tof_in_stream:
                integral_tof = abs(np.sum(data['tof']))
                _SQSbuffer__TOF_integral(integral_tof)
                _SQSbuffer__TOF_avg(data['tof'])
                avg_tof = np.squeeze(np.mean(_SQSbuffer__TOF_avg.data, axis=0)) 
                if tof_area_integrals:
                    #~ tof_data_for_int = np.squeeze(data['tof'])
                    tof_data_for_int = np.squeeze(avg_tof)
                    #~ print(tof_data_for_int.shape)
                    if True:
                        int_1 = abs(np.sum(tof_data_for_int[integral_range_1[0]-start_tof:integral_range_1[1]-start_tof]))
                        int_2 = abs(np.sum(tof_data_for_int[integral_range_2[0]-start_tof:integral_range_2[1]-start_tof]))
                        int_3 = abs(np.sum(tof_data_for_int[integral_range_3[0]-start_tof:integral_range_3[1]-start_tof]))
                    _SQSbuffer__TOF_integral_1(int_1)
                    _SQSbuffer__TOF_integral_2(int_1/int_3)
                    _SQSbuffer__TOF_integral_3(int_2/int_3)
                
                if integral_tof > 2e5:
                    _SQSbuffer__TOF_hits(1)
                else:
                    _SQSbuffer__TOF_hits(0)
            if gmd_in_stream:
                _SQSbuffer__GMD_history(data['gmd'][0])
            _SQSbuffer__counter(n)
            # Things for add next tick callback
            if n%5==0:
                if use_tof_cal_axis:
                    data_x_tof = data['x_tof_cal']
                else:
                    data_x_tof = data['x_tof']
                    
                callback_data_dict = dict()
                callback_data_dict["tof_trace"] = ( np.squeeze(data_x_tof) , np.squeeze(data['tof']))
                callback_data_dict["tof_integral"] = ( _SQSbuffer__counter.data , _SQSbuffer__TOF_integral.data )
                if tof_area_integrals:
                    callback_data_dict["tof_integral_1"] = ( _SQSbuffer__counter.data , _SQSbuffer__TOF_integral_1.data )
                    callback_data_dict["tof_integral_2"] = ( _SQSbuffer__counter.data , _SQSbuffer__TOF_integral_2.data )
                    callback_data_dict["tof_integral_3"] = ( _SQSbuffer__counter.data , _SQSbuffer__TOF_integral_3.data )
                
                callback_data_dict["tof_avg"] = ( np.squeeze(data_x_tof) , avg_tof )
                #~ callback_data_dict["gmd_history"] = ( _SQSbuffer__counter.data , _SQSbuffer__GMD_history.data )

                buffer_or_pipe_dict = dict()
                buffer_or_pipe_dict["tof_trace"] = _pipe__TOF_single
                buffer_or_pipe_dict["tof_integral"] = _pipe__TOF_integral
                if tof_area_integrals:
                    buffer_or_pipe_dict["tof_integral_1"] = _pipe__TOF_integral_1
                    buffer_or_pipe_dict["tof_integral_2"] = _pipe__TOF_integral_2
                    buffer_or_pipe_dict["tof_integral_3"] = _pipe__TOF_integral_3
                buffer_or_pipe_dict["tof_avg"] = _pipe__TOF_avg
                #buffer_or_pipe_dict["gmd_history"] = _pipe__GMD_history

                if 'all_updates_next_tick_callback' in locals():
                    if all_updates_next_tick_callback in doc.session_callbacks:
                        doc.remove_next_tick_callback(all_updates_next_tick_callback)
                all_updates_next_tick_callback = callback_data_dict_into_callback(buffer_or_pipe_dict, callback_data_dict, n )

            # Things for performance analysis
            ## TrainId
            trainId = str(data['tid'])

            perf.update_trainId(trainId) # give current train id to performance monitor for finding skipping of shots
            perf.time_for_loop_step() # tell performance monitor that this is the end of the for loop


# Helper to convert from holoviews to bokeh
def hv_to_bokeh_obj(hv_layout):
    # convert holoviews layout to bokeh object
    hv_plot = renderer.get_plot(hv_layout)
    return hv_plot.state

def pd_data_xy(x,y):
    # generates a pd dataframe (special data structure that holoviews likes) with x y data in the columns x and y
    return pd.DataFrame([(x,y)], columns=['x','y'])

def data_into_buffer_or_pipe(buffer_or_pipe, data,n):
    # pushes new data into pipe or buffer
    next_tick_callback = doc.add_next_tick_callback(partial(test_func,buffer_or_pipe,data,n))
    return next_tick_callback

def data_into_recent_hits_pipes(buffer_or_pipe_list, data,n):
    # pushes new data into pipe or buffer
    next_tick_callback = doc.add_next_tick_callback(partial(fill_recent_hits_pipes,buffer_or_pipe_list,data,n))
    return next_tick_callback

def callback_data_dict_into_callback( buffer_or_pipe_dict, callback_data_dict, n ):
    next_tick_callback = doc.add_next_tick_callback(partial(updateAllPlotPipes,buffer_or_pipe_dict,callback_data_dict, n))
    return next_tick_callback

@without_document_lock
def updateAllPlotPipes(buffer_or_pipe_dict, callback_data_dict, n):
    print("#####  "+str(n)+"  ######## Update all Plots Func @ n = "+ str(n))
    for key in buffer_or_pipe_dict:
        if key is not "pnCCD_recent_hits":
            buffer_or_pipe_dict[key].send(callback_data_dict[key])
        else:
            fill_recent_hits_pipes(buffer_or_pipe_dict[key],callback_data_dict[key], n)
    print(">>>>>>>  "+str(n)+"  <<<<<< Update all Plots Func @ n = "+ str(n))
    pass
@without_document_lock
def test_func(buffer_or_pipe,data, n):
    print("Called Test Func @ n = "+ str(n))
    buffer_or_pipe.send(data)
@without_document_lock
def fill_recent_hits_pipes(buffer_or_pipe_list,data, n):
    #print("#####  "+str(n)+"  ######## Called fill recent hits pipes @ n = "+ str(n))
    #print(data.shape)
    for i in range(len(buffer_or_pipe_list)):
        buffer_or_pipe_list[i].send(data[-i,:,:])


def test_func_debug(buffer_or_pipe,data,n):
    print("Called Test Func Debug")
    #print(data)
    buffer_or_pipe.send(data)
# plot tools functions
def largeData_line_plot(pipe_or_buffer, width=1500, height=400,ylim=(-500, 40),xlim=(start_tof,start_tof+N_datapts), xlabel="index", ylabel="TOF signal", cmap = ['blue'], title=None):
    TOF_dmap = hv.DynamicMap(hv.Curve, streams=[pipe_or_buffer])
    TOF_dmap_opt = datashade(TOF_dmap, streams=[PlotSize, RangeXY], dynamic=True, cmap = cmap)
    return hv_to_bokeh_obj( TOF_dmap_opt.opts(width=width,height=height,ylim=ylim,xlim=xlim, xlabel=xlabel, ylabel=ylabel, title = title) )

def smallData_line_plot(pipe_or_buffer, width=1500, height=400,ylim=(-500, 40),xlim=(start_tof,start_tof+N_datapts), xlabel="index", ylabel="TOF signal", title=None):
    TOF_dmap = hv.DynamicMap(hv.Curve, streams=[pipe_or_buffer]).redim.range().opts( norm=dict(framewise=True) ) #.redim.range().opts( norm=dict(framewise=True) ) makes x and y lim dynamic
    return hv_to_bokeh_obj( TOF_dmap.opts(width=width,height=height,ylim=ylim,xlim=xlim, xlabel=xlabel, ylabel=ylabel, title = title))

def pnCCDData_plot(pipe_or_buffer, width=500, height=500,ylim=(-0.5,0.5),xlim=(-0.5,0.5), title=None):
    TOF_dmap = hv.DynamicMap(hv.Image, streams=[pipe_or_buffer])
    #TOF_dmap_opt = rasterize(TOF_dmap)
    TOF_dmap_opt = TOF_dmap
    #TOF_dmap_opt = datashade(TOF_dmap, streams=[PlotSize, RangeXY], dynamic=True)
    return hv_to_bokeh_obj( TOF_dmap_opt.opts(width=width,height=height,ylim=ylim,xlim=xlim, title = title, colorbar = True) )

def start_stop_dataThread():
    global makeBigData_stop
    if not makeBigData_stop:
        makeBigData_stop = True
    else:
        thread.start()

# Data buffers for live stream

buffer_len = 1500
_SQSbuffer__TOF_integral = online.DataBuffer(buffer_len)
_SQSbuffer__TOF_integral_1 = online.DataBuffer(buffer_len)
_SQSbuffer__TOF_integral_2 = online.DataBuffer(buffer_len)
_SQSbuffer__TOF_integral_3 = online.DataBuffer(buffer_len)
_SQSbuffer__TOF_avg = online.DataBuffer(100)
_SQSbuffer__TOF_hit_trace = online.DataBuffer(1)
_SQSbuffer__TOF_hits = online.DataBuffer(1000)
_SQSbuffer__GMD_history = online.DataBuffer(buffer_len)
_SQSbuffer__TOF_hits = online.DataBuffer(10)
_SQSbuffer__counter = online.DataBuffer(buffer_len)
print("...2")

# Data pipes and buffers for plots
## pipes provide a full update of data to the underlying object eg. plot
## buffers add only a single value to the plot and may kick one out when number of elements in the buffer has reached the length/size of the buffer
_pipe__TOF_single = Pipe(data=[])
_pipe__TOF_hit_trace = Pipe(data=[])
_pipe__TOF_avg = Pipe(data=[])
_pipe__TOF_integral = Pipe(data=[])
_pipe__TOF_integral_1 = Pipe(data=[])
_pipe__TOF_integral_2 = Pipe(data=[])
_pipe__TOF_integral_3 = Pipe(data=[])
_pipe__GMD_history = Pipe(data=[])

# SETUP PLOTS
print("...3")
# example for coupled plots
#         layout = hv.Layout(largeData_line_plot(_pipe__TOF_single, title="TOF single shots - LIVE") + largeData_line_plot(_pipe__TOF_single, title="TOF single shots - LIVE 2", cmap=['red'])).cols(1)
## TOF
bokeh_live_tof =  largeData_line_plot(_pipe__TOF_single, title="TOF single shots - LIVE", width = 1000, height=500, xlim = xlim_tof)
bokeh_avg_tof =  largeData_line_plot(_pipe__TOF_avg, title="TOF runnign avg", width = 1000, height=500, xlim = xlim_tof)
#~ bokeh_avg_tof =  largeData_line_plot(_pipe__TOF_avg, title="TOF runnign avg", width = 1000, height=500)


bokeh_buffer_tof_integral = smallData_line_plot(_pipe__TOF_integral, title="TOF trace full range integral (absolute)", xlim=(None,None), ylim=(0, None), width = 400, height = 250)
bokeh_buffer_tof_integral_1 = smallData_line_plot(_pipe__TOF_integral_1, title="TOF trace integral range 1", xlim=(None,None), ylim=(None, None), width = 400, height = 250)
bokeh_buffer_tof_integral_2 = smallData_line_plot(_pipe__TOF_integral_2, title="TOF trace integral range 1 / 3", xlim=(None,None), ylim=(None, None), width = 600, height = 250)
bokeh_buffer_tof_integral_3 = smallData_line_plot(_pipe__TOF_integral_3, title="TOF trace integral range 2 / 3", xlim=(None,None), ylim=(None, None), width = 600, height = 250)

## GMD
bokeh_buffer_gmd_history = smallData_line_plot(_pipe__GMD_history, title="pulseE last 1000 Trains", xlim=(None,None), ylim=(0, None), width = 400, height =250)

## SET UP Additional Widgets
bokeh_button_StartStop = Button(label = "Start / Stop", button_type="success")
bokeh_button_StartStop.on_click(start_stop_dataThread)
# SET UP BOKEH LAYOUT
#
bokeh_row_1 = row(bokeh_live_tof,bokeh_avg_tof)
bokeh_row_2 = row(bokeh_buffer_tof_integral,bokeh_buffer_gmd_history,bokeh_buffer_tof_integral_1,bokeh_buffer_tof_integral_2,bokeh_buffer_tof_integral_3)
bokeh_row_interact  = bokeh_button_StartStop
bokeh_layout = column(bokeh_row_1,bokeh_row_2, bokeh_row_interact)
print("...4")
# add bokeh layout to current doc
doc.add_root(bokeh_layout)
print("...5")
# Start Thread for Handling of the Live Data Strem
thread = Thread(target=makeBigData)
thread.start()
