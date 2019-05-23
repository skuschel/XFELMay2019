#file to define the settings. We can make this load from a config file later

# Load experiment config dict into module wide variable
defaultConf = dict()

#Define the defaults for all the detector settings
defaultConf['tofRange'] = [262000,290000] #the range where interesting data appears
defaultConf['tofBaseEnd'] = 100 # the first n samples to consider as baseline

#device addresses
defaultConf['imageDevice'] = 'SQS_DPU_LIC/CAM/YAG_UPSTR:output'
defaultConf['tofDevice'] = 'SQS_DIGITIZER_UTC1/ADC/1:network'
defaultConf['pulseEDevice'] = 'SA3_XTD10_XGM/XGM/DOOCS'
