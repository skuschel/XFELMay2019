function out = tof_read(path)
    files = get_files(path, 'DA02');
        
    out.data = [];
    out.trainId = [];
    
    for i=1:numel(files)
        path_full = sprintf('%s/%s', files(i).folder, files(i).name);

        TOF_data     = '/INSTRUMENT/SQS_DIGITIZER_UTC1/ADC/1:network/digitizers/channel_1_A/raw/samples';
        TOF_trainId  = '/INSTRUMENT/SQS_DIGITIZER_UTC1/ADC/1:network/digitizers/trainId';
    
        out.data   = cat(2, out.data, h5read(path_full, TOF_data));
        out.trainId = [out.trainId; h5read(path_full, TOF_trainId)]; 

    end
end