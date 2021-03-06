'''
Program Name: get_data_file.py
Contact(s): Mallory Row
Abstract: This script is run by all scripts in scripts/.
          This gets the necessary data files to run
          the METplus use case.
'''

from __future__ import (print_function, division)
import os
import subprocess
import datetime
from time import sleep

print("BEGIN: "+os.path.basename(__file__))

# Read in environment variables
RUN = os.environ['RUN']
model_list = os.environ['model_list'].split(' ')
model_dir_list = os.environ['model_dir_list'].split(' ')
model_arch_dir_list = os.environ['model_arch_dir_list'].split(' ')
model_fileformat_list = os.environ['model_fileformat_list'].split(' ')
model_data_run_hpss = os.environ['model_data_runhpss']
start_date = os.environ['start_date']
end_date = os.environ['end_date']
make_met_data_by = os.environ['make_met_data_by']
plot_by = os.environ['plot_by']
model_hpssdir_list = os.environ['model_hpssdir_list'].split(' ')
machine = os.environ['machine']

# No HPSS access from Orion
if machine == 'ORION':
    print("WARNING: Orion does not currently have access to HPSS..."
          +"setting model_data_runhpss to NO")
    model_data_run_hpss = 'NO'

# Set HPSS location for production data
hpss_prod_base_dir = '/NCEPPROD/hpssprod/runhistory'

def get_time_info(start_date, end_date, 
                  start_hr, end_hr, hr_inc, 
                  fhr_list, make_met_data_by):
    """! This creates a list of dictionaries containing information
         on the valid dates and times, the initialization dates
         and times, and forecast hour pairings
        
         Args:
             start_date       - string of the verification start
                                date
             end_date         - string of the verification end
                                date
             start_hr         - string of the verification start
                                hour
             end_hr           - string of the verification end
                                hour
             hr_inc           - string of the increment between
                                start_hr and end_hr
             fhr_list         - list of strings of the forecast
                                hours to verify
             make_met_data_by - string defining by what type
                                date and times to create METplus
                                data
             
         Returns:
             time_info        - list of dictionaries with the valid,
                                initalization, and forecast hour
                                pairings
    """
    sdate = datetime.datetime(int(start_date[0:4]), int(start_date[4:6]), 
                              int(start_date[6:]), int(start_hr))
    edate = datetime.datetime(int(end_date[0:4]), int(end_date[4:6]), 
                              int(end_date[6:]), int(end_hr))
    date_inc = datetime.timedelta(seconds=int(hr_inc))
    time_info = []
    date = sdate
    while date <= edate:
        if make_met_data_by == 'VALID':
            validtime = date
        elif make_met_data_by == 'INIT':
            inittime = date
        for fhr in fhr_list:
            if fhr == 'anl':
                lead = '00'
            else:
                lead = fhr
            if make_met_data_by == 'VALID':
                inittime = validtime - datetime.timedelta(hours=int(lead))
            elif make_met_data_by == 'INIT':
                validtime = inittime + datetime.timedelta(hours=int(lead))
            to = {}
            to['validtime'] = validtime
            to['inittime'] = inittime
            to['lead'] = lead
            time_info.append(to)
        date = date + date_inc
    return time_info

def format_filler(file_format, valid_time, init_time, lead):
    """! This creates a list of objects containing information
         on the valid dates and times, the initialization dates
         and times, and forecast hour pairings
        
         Args:
             file_format        - string of file naming
                                  convention
             valid_time         - datetime object of the 
                                  valid time
             init_time          - datetime object of the
                                  initialization time
             lead               - string of the forecast
                                  lead
          
         Returns:
             filled_file_format - string of file_format
                                  filled in with verifying
                                  time information
    """
    filled_file_format = ''
    file_format_opt_list = ['lead', 'valid', 'init', 'cycle']
    for file_format_chunk in file_format.split('/'):
        filled_file_format_chunk = file_format_chunk
        for file_format_opt in file_format_opt_list:
            nfile_format_opt = (
                filled_file_format_chunk.count('{'+file_format_opt+'?fmt=')
            )
            if nfile_format_opt > 0:
               file_format_opt_count = 1
               while file_format_opt_count <= nfile_format_opt:
                   file_format_opt_count_fmt = (
                       filled_file_format_chunk \
                       .partition('{'+file_format_opt+'?fmt=')[2] \
                       .partition('}')[0]
                   )
                   if file_format_opt == 'valid':
                       replace_file_format_opt_count = valid_time.strftime(
                           file_format_opt_count_fmt
                       )
                   elif file_format_opt == 'lead':
                       if file_format_opt_count_fmt == '%1H':
                           if int(lead) < 10:
                               replace_file_format_opt_count = lead[1]
                           else:
                               replace_file_format_opt_count = lead
                       elif file_format_opt_count_fmt == '%2H':
                           replace_file_format_opt_count = lead.zfill(2)
                       elif file_format_opt_count_fmt == '%3H':
                           replace_file_format_opt_count = lead.zfill(3)
                       else:
                           replace_file_format_opt_count = lead
                   elif file_format_opt in ['init', 'cycle']:
                       replace_file_format_opt_count = init_time.strftime(
                           file_format_opt_count_fmt
                       )
                   filled_file_format_chunk = filled_file_format_chunk.replace(
                       '{'+file_format_opt+'?fmt='
                       +file_format_opt_count_fmt+'}',
                       replace_file_format_opt_count
                   )
                   file_format_opt_count+=1
        filled_file_format = os.path.join(filled_file_format, filled_file_format_chunk)
    return filled_file_format

def get_hpss_data(hpss_job_filename, link_data_dir, link_data_file,
                  hpss_tar, hpss_file):
    """! This creates a job card with the necessary information
         to retrieve a file from HPSS. It then submits this
         job card to the transfer queue and the designating
         wall time. 
        
         Args:
             hpss_job_filename - string of the path of the
                                 HPSS job card name
             link_data_dir     - string of the path to the
                                 directory where the HPSS
                                 retrieved file will be 
                                 saved
             link_data_file    - string of the file name
                                 the HPSS retrieved file
                                 will be saved as
             hpss_tar          - string of the tar file
                                 path where hpss_file
                                 is located
             hpss_file         - string of the file name
                                 to be retrieved from HPSS
          
         Returns:
    """
    # Read in environment variables
    HTAR = os.environ['HTAR']
    hpss_walltime = os.environ['hpss_walltime']
    machine = os.environ['machine']
    QUEUESERV = os.environ['QUEUESERV']
    ACCOUNT = os.environ['ACCOUNT']
    # Set up job wall time information
    walltime_seconds = (
        datetime.timedelta(minutes=int(hpss_walltime)).total_seconds()
    )
    walltime = (datetime.datetime.min 
                + datetime.timedelta(minutes=int(hpss_walltime))).time()
    if os.path.exists(hpss_job_filename):
        os.remove(hpss_job_filename)
    # Create job card
    with open(hpss_job_filename, 'a') as hpss_job_file:
        hpss_job_file.write('#!/bin/sh'+'\n')
        hpss_job_file.write('cd '+link_data_dir+'\n')
        hpss_job_file.write(HTAR+' -xf '+hpss_tar+' ./'+hpss_file+'\n')
        if 'pgrb2' in hpss_file:
            cnvgrib = os.environ['CNVGRIB']
            hpss_job_file.write(cnvgrib+' -g21 '+hpss_file+' '
                                +link_data_file+' > /dev/null 2>&1\n')
            hpss_job_file.write('rm -r '+hpss_file.split('/')[0])
        elif 'trackatcfunix' in hpss_file:
            hpss_job_file.write(HTAR+' -xf '+hpss_tar+' ./'
                                +hpss_file.replace('avno', 'avn')+'\n')
            hpss_job_file.write('cp '+hpss_file.split('avn')[0]+'avn* '
                                +link_data_file+'\n')
            hpss_job_file.write('rm -r '+hpss_file.split('/')[0]+'\n')
            model_atcf_abbrv = (link_data_file.split('/')[-2])[0:4].upper()
            hpss_job_file.write('sed -i s/AVNO/'+model_atcf_abbrv+'/g '
                                +link_data_file)
        else:
            if hpss_file[0:5] != 'ccpa.':
                hpss_job_file.write('cp '+hpss_file+' '+link_data_file+'\n')
                hpss_job_file.write('rm -r '+hpss_file.split('/')[0])
    # Submit job card
    os.chmod(hpss_job_filename, 0o755)
    hpss_job_output = hpss_job_filename.replace('.sh', '.out')
    if os.path.exists(hpss_job_output):
        os.remove(hpss_job_output)
    hpss_job_name = hpss_job_filename.rpartition('/')[2].replace('.sh', '')
    print("Submitting "+hpss_job_filename+" to "+QUEUESERV)
    print("Output sent to "+hpss_job_output)
    if machine == 'WCOSS_C':
        os.system('bsub -W '+walltime.strftime('%H:%M')+' -q '+QUEUESERV+' '
                  +'-P '+ACCOUNT+' -o '+hpss_job_output+' -e '
                  +hpss_job_output+' '
                  +'-J '+hpss_job_name+' -R rusage[mem=2048] '+hpss_job_filename)
        job_check_cmd = ('bjobs -a -u '+os.environ['USER']+' '
                         +'-noheader -J '+hpss_job_name
                         +'| grep "RUN\|PEND" | wc -l')
    elif machine == 'WCOSS_DELL_P3':
        os.system('bsub -W '+walltime.strftime('%H:%M')+' -q '+QUEUESERV+' '
                  +'-P '+ACCOUNT+' -o '+hpss_job_output+' -e '
                  +hpss_job_output+' '
                  +'-J '+hpss_job_name+' -M 2048 -R "affinity[core(1)]" '
                  +hpss_job_filename)
        job_check_cmd = ('bjobs -a -u '+os.environ['USER']+' '
                         +'-noheader -J '+hpss_job_name
                         +'| grep "RUN\|PEND" | wc -l')
    elif machine == 'HERA':
        os.system('sbatch --ntasks=1 --time='+walltime.strftime('%H:%M:%S')+' '
                  +'--partition='+QUEUESERV+' --account='+ACCOUNT+' '
                  +'--output='+hpss_job_output+' '
                  +'--job-name='+hpss_job_name+' '+hpss_job_filename)
        job_check_cmd = ('squeue -u '+os.environ['USER']+' -n '
                         +hpss_job_name+' -t R,PD -h | wc -l')
    elif machine == 'ORION':
        print("ERROR: No HPSS access from Orion.")
    if machine != 'ORION':
        sleep_counter, sleep_checker = 1, 10
        while (sleep_counter*sleep_checker) <= walltime_seconds:
            sleep(sleep_checker)
            print("Walltime checker: "+str(sleep_counter*sleep_checker)+" "
                  +"out of "+str(int(walltime_seconds))+" seconds")
            check_job = subprocess.check_output(job_check_cmd, shell=True)
            if check_job[0] == '0':
                break
            sleep_counter+=1

def set_up_gfs_hpss_info(init_time, hpss_dir, hpss_file_prefix,
                         hpss_file_suffix, link_data_dir):
    """! This sets up HPSS and job information specifically
         for getting GFS data from HPSS.
        
         Args:
             init_time         - datetime object of the
                                 initialization time
             hpss_dir          - string of the base HPSS
                                 directory path
             hpss_file_prefix  - string of information at
                                 the beinginng of the HPSS
                                 file
             hpss_file_suffix  - string of information
                                 on the end of the HPSS
                                 file
             link_data_dir     - string of the path to the
                                 directory where the HPSS
                                 retrieved file will be 
                                 saved
          
         Returns:
             hpss_tar          - string of the tar file
                                 path where hpss_file
                                 is located
             hpss_file         - string of the file name
                                 to be retrieved from HPSS
             hpss_job_filename - string of the path of the
                                 HPSS job card name

    """
    YYYYmmddHH = init_time.strftime('%Y%m%d%H')
    YYYYmmdd = init_time.strftime('%Y%m%d')
    YYYYmm = init_time.strftime('%Y%m')
    YYYY = init_time.strftime('%Y')
    mm = init_time.strftime('%m')
    dd = init_time.strftime('%d')
    HH = init_time.strftime('%H')
    if 'NCEPPROD' in hpss_dir:
        # Operational GFS HPSS archive only for pgrb2 files
        # no cyclone track files
        hpss_date_dir = os.path.join(hpss_dir, 'rh'+YYYY, YYYYmm,
                                     YYYYmmdd)
        if int(YYYYmmdd) >= 20200226:
            hpss_tar = os.path.join(hpss_date_dir,
                                    'com_gfs_prod_'+hpss_file_prefix+'.'
                                    +YYYYmmdd+'_'+HH+'.'+hpss_file_prefix
                                    +'_pgrb2.tar')
            hpss_file = (
                hpss_file_prefix+'.'+YYYYmmdd+'/'+HH+'/'
                +hpss_file_prefix+'.t'+HH
                +'z.pgrb2.0p25.'+hpss_file_suffix
                )
        elif int(YYYYmmdd) >= 20190612 and int(YYYYmmdd) < 20200226: 
            hpss_tar = os.path.join(hpss_date_dir,
                                    'gpfs_dell1_nco_ops_com_gfs_prod_'
                                    +hpss_file_prefix+'.'
                                    +YYYYmmdd+'_'+HH+'.'+hpss_file_prefix
                                    +'_pgrb2.tar')
            hpss_file = (
                hpss_file_prefix+'.'+YYYYmmdd+'/'+HH+'/'
                +hpss_file_prefix+'.t'+HH
                +'z.pgrb2.0p25.'+hpss_file_suffix
                )
        elif int(YYYYmmdd) >= 20170720 and int(YYYYmmdd) < 20190612:
            hpss_tar = os.path.join(hpss_date_dir, 
                                    'gpfs_hps_nco_ops_com_gfs_prod_'
                                    +hpss_file_prefix+'.'
                                    +YYYYmmddHH+'.pgrb2_0p25.tar')
            hpss_file = (
                hpss_file_prefix+'.t'+HH+'z.pgrb2.0p25.'
                +hpss_file_suffix
            )
        elif int(YYYYmmdd) >= 20160510 and int(YYYYmmdd) < 20170720:
            hpss_tar = os.path.join(hpss_date_dir,
                                    'com2_gfs_prod_'+hpss_file_prefix+'.'
                                    +YYYYmmddHH+'.pgrb2_0p25.tar')
            hpss_file = (
                hpss_file_prefix+'.t'+HH+'z.pgrb2.0p25.'
                +hpss_file_suffix
            )
        else:
            hpss_tar = os.path.join(hpss_date_dir,
                                    'com_gfs_prod_'+hpss_file_prefix+'.'
                                    +YYYYmmddHH+'.pgrb2_0p25.tar')
            hpss_file = (
                hpss_file_prefix+'.t'+HH+'z.pgrb2.0p25.'
                +hpss_file_suffix
            )
        if hpss_file_prefix == 'enkfgdas':
            hpss_tar = hpss_tar.replace('_pgrb2.tar', '.tar') \
                       .replace('.pgrb2_0p25.tar', '.tar')
            hpss_file = hpss_file.replace('pgrb2.0p25.','') \
                        .replace(hpss_file_prefix+'.t', 'gdas.t')
    else:
        if hpss_file_prefix == 'gfs':
            hpss_tar = os.path.join(hpss_dir, name, YYYYmmddHH, 'gfsa.tar')
        elif hpss_file_prefix == 'gdas':
            hpss_tar = os.path.join(hpss_dir, name, YYYYmmddHH, 'gdas.tar')
        elif hpss_file_prefix == 'enkfgdas':
            hpss_tar = os.path.join(hpss_dir, name, YYYYmmddHH,
                                    'enkfgdas.tar')
        if hpss_file_suffix == 'cyclone.trackatcfunix':
            hpss_file = ( 
                hpss_file_prefix+'.'+YYYYmmdd+'/'+HH+'/'
                +'avno.t'+HH+'z.'+hpss_file_suffix
            )
        elif hpss_file_prefix == 'enkfgdas':
            hpss_file = (
                hpss_file_prefix+'.'+YYYYmmdd+'/'+HH+'/'
                +'gdas.t'+HH+'z.'+hpss_file_suffix
            )
        else:
            hpss_file = (
                hpss_file_prefix+'.'+YYYYmmdd+'/'+HH+'/'
                +hpss_file_prefix+'.t'+HH+'z.pgrb2.0p25.'+hpss_file_suffix
            )
    hpss_job_filename = os.path.join(
        link_data_dir, 'HPSS_jobs', 'HPSS_'+hpss_tar.rpartition('/')[2]
        +'_'+hpss_file.replace('/', '_')+'.sh'
    )
    return hpss_tar, hpss_file, hpss_job_filename

def convert_grib2_grib1(grib2_file, grib1_file):
    """! This converts GRIB2 data to GRIB1
        
         Args:
             grib2_file - string of the path to
                          the GRIB2 file to
                          convert
             grib1_file - string of the path to
                          save the converted GRIB1
                          file
 
         Returns:
    """
    print("Converting GRIB2 file "+grib2_file+" "
          +"to GRIB1 file "+grib1_file)
    cnvgrib = os.environ['CNVGRIB']
    os.system(cnvgrib+' -g21 '+grib2_file+' '
              +grib1_file+' > /dev/null 2>&1')

grib2_file_names = ['grib2', 'grb2']
if RUN == 'grid2grid_step1':
    # Read in environment variables
    anl_name = os.environ['g2g1_anl_name']
    anl_file_format_list = os.environ['g2g1_anl_fileformat_list'].split(' ')
    if make_met_data_by == 'VALID':
        start_hr = os.environ['g2g1_valid_hr_beg']
        end_hr = os.environ['g2g1_valid_hr_end']
        hr_inc = os.environ['g2g1_valid_hr_inc']
    else:
        start_hr = os.environ['g2g1_init_hr_beg']
        end_hr = os.environ['g2g1_init_hr_end']
        hr_inc = os.environ['g2g1_init_hr_inc']
    fhr_list = os.environ['g2g1_fhr_list'].split(', ')
    type_list = os.environ['g2g1_type_list'].split(' ')
    # Get date and time information
    time_info = get_time_info(start_date, end_date, start_hr, end_hr, hr_inc, 
                              fhr_list, make_met_data_by)
    # Get model forecast files
    cwd = os.getcwd()
    for name in model_list:
        index = model_list.index(name)
        dir = model_dir_list[index]
        file_format = model_fileformat_list[index]
        if 'gfs' in file_format:
            dump = 'gfs'
        elif 'gdas' in file_format:
            dump = 'gdas'
        hpss_dir = model_hpssdir_list[index]
        link_model_data_dir = os.path.join(cwd, 'data', name)
        if not os.path.exists(link_model_data_dir):
            os.makedirs(link_model_data_dir)
            os.makedirs(
                os.path.join(link_model_data_dir, 'HPSS_jobs')
            )
        for time in time_info:
            valid_time = time['validtime']
            init_time = time['inittime']
            lead = time['lead']
            if init_time.strftime('%H') in ['03', '09', '15', '21']:
                continue
            else:
                link_model_forecast_file = os.path.join(
                    link_model_data_dir, 
                    'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                )
                if not os.path.exists(link_model_forecast_file):
                    model_forecast_filename = format_filler(file_format,
                                                            valid_time, 
                                                            init_time, lead)
                    model_forecast_file = os.path.join(dir, name,
                                                       model_forecast_filename)
                    if os.path.exists(model_forecast_file):
                        if any(
                            g in model_forecast_file for g in grib2_file_names
                        ):
                            convert_grib2_grib1(model_forecast_file, 
                                                link_model_forecast_file)
                        else:
                            os.system('ln -sf '+model_forecast_file+' '
                                      +link_model_forecast_file)
                    else:
                        if model_data_run_hpss == 'YES':
                            print("Did not find "+model_forecast_file+" "
                                  +"online...going to try to get file "
                                  +"from HPSS")
                            hpss_tar, hpss_file, hpss_job_filename = (
                                set_up_gfs_hpss_info(init_time, hpss_dir,
                                                     dump, 
                                                     'f'+lead.zfill(3), 
                                                     link_model_data_dir)
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_model_data_dir, 
                                          link_model_forecast_file,
                                          hpss_tar, hpss_file)
                    if not os.path.exists(link_model_forecast_file):
                        if model_data_run_hpss == 'YES':
                            print("WARNING: "+model_forecast_file+" "
                                  +"does not exist and did not find "
                                  +"HPSS file "+hpss_file+" from "
                                  +hpss_tar+" or walltime exceeded")
                        else:
                            print("WARNING: "+model_forecast_file+" "
                                  +"does not exist")
    # Get model "truth" files
    valid_time_list = []
    for time in time_info:
        valid_time = time['validtime']
        if valid_time not in valid_time_list:
            valid_time_list.append(valid_time)
    for name in model_list:
        index = model_list.index(name)
        dir = model_dir_list[index]
        if 'gfs' in anl_name or len(anl_file_format_list) == 1:
            anl_file_format = anl_file_format_list[0]
        else:
            anl_file_format = anl_file_format_list[index]
        if 'gfs' in anl_file_format:
            anl_dump = 'gfs'
        elif 'gdas' in anl_file_format:
            anl_dump = 'gdas'
        hpss_dir = model_hpssdir_list[index]
        file_format = model_fileformat_list[index]
        if 'gfs' in file_format:
            dump = 'gfs'
        elif 'gdas' in file_format:
            dump = 'gdas'
        link_model_data_dir = os.path.join(cwd, 'data', name)
        if not os.path.exists(link_model_data_dir):
            os.makedirs(link_model_data_dir)
            os.makedirs(
                os.path.join(link_model_data_dir, 'HPSS_jobs')
            )
        for valid_time in valid_time_list:
            link_anl_file = os.path.join(
                link_model_data_dir,
                'anl.'+valid_time.strftime('%Y%m%d%H')
            )
            if not os.path.exists(link_anl_file):
                anl_filename = format_filler(anl_file_format,
                                             valid_time, 
                                             init_time, lead)
                if anl_name == 'self_anl' or anl_name == 'self_f00':
                    anl_dir = os.path.join(dir, name)
                elif anl_name == 'gfs_anl' or anl_name == 'gfs_f00':
                    anl_dir = os.path.join(os.environ['gstat'], 'gfs')
                else:
                    print("ERROR: "+anl_name+" is not a valid option "
                          +"for g2g1_anl_name")
                    exit(1)
                anl_file = os.path.join(anl_dir, anl_filename)
                if os.path.exists(anl_file):
                    anl_found = True
                    if any(g in anl_file for g in grib2_file_names):
                        convert_grib2_grib1(anl_file,
                                            link_anl_file) 
                    else:
                        os.system('ln -sf '+anl_file+' '+link_anl_file)
                else:
                    if model_data_run_hpss == 'YES':
                        print("Did not find "+anl_file+" "
                              +"online...going to try to get file from HPSS")
                        if 'self' in anl_name:
                            hpss_dir = hpss_dir
                        elif 'gfs' in anl_name:
                            hpss_dir = '/NCEPPROD/hpssprod/runhistory'
                        hpss_tar, hpss_file, hpss_job_filename = (
                                set_up_gfs_hpss_info(valid_time, hpss_dir,
                                                     anl_dump, 'anl', 
                                                     link_model_data_dir)
                        )
                        get_hpss_data(hpss_job_filename,
                                      link_model_data_dir, link_anl_file,
                                      hpss_tar, hpss_file)
                    else:
                        anl_found = False 
                if not os.path.exists(link_anl_file):
                     if model_data_run_hpss == 'YES':
                         error_msg = ('WARNING: '+anl_file+' does not exist '
                                      +'and did not find HPSS file '
                                      +hpss_file+' from '+hpss_tar+' or '
                                      +'walltime exceeded')
                     else:
                         error_msg = 'WARNING: '+anl_file+' does not exist'
                     print(error_msg)
                     anl_found = False
                     error_dir = os.path.join(link_model_data_dir)
                     error_file = os.path.join(
                         error_dir,
                         'error_anl_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                     )
                     if not os.path.exists(error_file):
                         with open(error_file, 'a') as file:
                             file.write(error_msg)
                else:
                     anl_found = True
                if anl_found == False:
                     print("Analysis file not found..."
                           +"will try to link f00 instead")
                     link_f00_file = os.path.join(
                         link_model_data_dir,
                         'f00.'+valid_time.strftime('%Y%m%d%H')
                     )
                     if os.path.exists(link_f00_file):
                         os.system('ln -sf '+link_f00_file+' '+link_anl_file)
                     else:
                         f00_filename = format_filler(file_format,
                                                      valid_time, valid_time,
                                                      '00')
                         f00_file = os.path.join(dir, name,
                                                 f00_filename)
                         if os.path.exists(f00_file):
                             if any(
                                 g in f00_file for g in grib2_file_names
                             ):
                                 convert_grib2_grib1(f00_file,
                                                     link_anl_file)
                                 convert_grib2_grib1(f00_file,
                                                     link_f00_file)
                             else:
                                 os.system('ln -sf '+f00_file
                                           +' '+link_anl_file)
                                 os.system('ln -sf '+f00_file
                                           +' '+link_f00_file)
                         else:
                             if model_data_run_hpss == 'YES':
                                 hpss_tar, hpss_file, hpss_job_filename = (
                                     set_up_gfs_hpss_info(init_time, hpss_dir,
                                                          dump, 'f000',
                                                          link_model_data_dir)
                                 )
                                 get_hpss_data(hpss_job_filename,
                                               link_model_data_dir,
                                               link_anl_file,
                                               hpss_tar, hpss_file)
                                 if os.path.exists(link_anl_file):
                                     os.system('ln -sf '+link_anl_file+' '
                                               +link_f00_file)
                         if not os.path.exists(link_anl_file):
                             print("Unable to link f00 file as analysis")
            if 'sfc' in type_list:
                link_f00_file = os.path.join(
                    link_model_data_dir,
                    'f00.'+valid_time.strftime('%Y%m%d%H')
                )
                if not os.path.exists(link_f00_file):
                    f00_filename = format_filler(file_format,
                                                 valid_time, valid_time, '00')
                    f00_file = os.path.join(dir, name,
                                            f00_filename)
                    if os.path.exists(f00_file):
                        if any(
                            g in f00_file for g in grib2_file_names
                        ):
                            convert_grib2_grib1(f00_file,
                                                link_f00_file)
                        else:  
                            os.system('ln -sf '+f00_file+' '+link_f00_file)
                    else:
                        if model_data_run_hpss == 'YES':
                            print("Did not find "+f00_file+" "
                                  +"online...going to try to get file "
                                  +"from HPSS")
                            hpss_tar, hpss_file, hpss_job_filename = (
                                set_up_gfs_hpss_info(init_time, hpss_dir,
                                                     dump, 'f000', 
                                                     link_model_data_dir)
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_model_data_dir, link_f00_file,
                                          hpss_tar, hpss_file)
                    if not os.path.exists(link_f00_file):
                        if model_data_run_hpss == 'YES':
                           error_msg = ('WARNING: '+f00_file+' does not exist '
                                        +'and did not find HPSS file '
                                        +hpss_file+' from '+hpss_tar+' or '
                                        +'walltime exceeded')
                        else:
                            error_msg = 'WARNING: '+f00_file+' does not exist'
                        print(error_msg)
                        error_dir = os.path.join(link_model_data_dir)
                        error_file = os.path.join(
                            error_dir,
                            'error_f00_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                        )
                        if not os.path.exists(error_file):
                            with open(error_file, 'a') as file:
                                file.write(error_msg)
elif RUN == 'grid2grid_step2':
    # Read in environment variables
    type_list = os.environ['g2g2_type_list'].split(' ')
    gather_by_list = os.environ['g2g2_gather_by_list'].split(' ')
    if plot_by == 'VALID':
        start_hr = os.environ['g2g2_valid_hr_beg']
        end_hr = os.environ['g2g2_valid_hr_end']
        hr_inc = os.environ['g2g2_valid_hr_inc']
    else:
        start_hr = os.environ['g2g2_init_hr_beg']
        end_hr = os.environ['g2g2_init_hr_end']
        hr_inc = os.environ['g2g2_init_hr_inc']
    fhr_list = os.environ['g2g2_fhr_list'].split(', ')
    # Get date and time information
    time_info = get_time_info(start_date, end_date, start_hr, end_hr, hr_inc,
                              fhr_list, plot_by)
    # Get archive MET .stat files
    cwd = os.getcwd()
    for name in model_list:
        index = model_list.index(name)
        if len(model_arch_dir_list) != len(model_list):
            arch_dir = model_arch_dir_list[0]
        else:
            arch_dir = model_arch_dir_list[index]
        if len(gather_by_list) != len(model_list):
            gather_by = gather_by_list[0]
        else:
            gather_by = gather_by_list[index]
        for type in type_list:
            full_arch_dir = os.path.join(arch_dir, 'metplus_data', 
                                         'by_'+gather_by, 'grid2grid',
                                          type)
            link_model_data_dir = os.path.join(cwd, 'data', name, type)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
            for time in time_info:
                valid_time = time['validtime']
                init_time = time['inittime']
                lead = time['lead']
                if gather_by == 'VALID' or gather_by == 'VSDB':
                    stat_file = os.path.join(full_arch_dir, 
                                             valid_time.strftime('%H')+'Z', 
                                             name, name+'_'
                                             +valid_time.strftime('%Y%m%d')
                                             +'.stat')
                    link_stat_file = os.path.join(link_model_data_dir, name
                                                  +'_valid'+valid_time \
                                                  .strftime('%Y%m%d')
                                                  +'_valid'+valid_time \
                                                  .strftime('%H')+'.stat')
                elif gather_by == 'INIT':
                    stat_file = os.path.join(full_arch_dir, 
                                             init_time.strftime('%H')+'Z', 
                                             name, name+'_'
                                             +init_time.strftime('%Y%m%d')
                                             +'.stat')
                    link_stat_file = os.path.join(link_model_data_dir, name
                                                  +'_init'+init_time \
                                                  .strftime('%Y%m%d')
                                                  +'_init'+init_time \
                                                  .strftime('%H')+'.stat')
                if not os.path.exists(link_stat_file):
                    if os.path.exists(stat_file):
                        os.system('ln -sf '+stat_file+' '
                                  +link_stat_file)
                    else:
                        print("WARNING: "+stat_file+" "
                              +"does not exist")
elif RUN == 'grid2obs_step1':
    # Read in environment variables
    type_list = os.environ['g2o1_type_list'].split(' ')
    prepbufr_prod_upper_air_dir = os.environ['prepbufr_prod_upper_air_dir']
    prepbufr_prod_conus_sfc_dir = os.environ['prepbufr_prod_conus_sfc_dir']
    prepbufr_arch_dir = os.environ['prepbufr_arch_dir']
    prepbufr_run_hpss = os.environ['g2o1_prepbufr_data_runhpss']
    # No HPSS access from Orion
    if machine == 'ORION':
        print("WARNING: Orion does not currently have access to HPSS..."
              +"setting g2o1_prepbufr_data_runhpss to NO")
        prepbufr_run_hpss = 'NO'
    for type in type_list:
        # Get date and time information
        fhr_list_type = os.environ['g2o1_fhr_list_'+type].split(', ')
        if make_met_data_by == 'VALID':
            start_hr_type = os.environ['g2o1_valid_hr_beg_'+type]
            end_hr_type = os.environ['g2o1_valid_hr_end_'+type]
            hr_inc_type = os.environ['g2o1_valid_hr_inc_'+type]
        else:
            start_hr_type = os.environ['g2o1_init_hr_beg']
            end_hr_type = os.environ['g2o1_init_hr_end']
            hr_inc_type = os.environ['g2o1_init_hr_inc'] 
        time_info = get_time_info(start_date, end_date, start_hr_type,
                                  end_hr_type, hr_inc_type, fhr_list_type,
                                  make_met_data_by)
        # Get model forecast files
        cwd = os.getcwd()
        for name in model_list:
            index = model_list.index(name)
            dir = model_dir_list[index]
            file_format = model_fileformat_list[index]
            if 'gfs' in file_format:
                dump = 'gfs'
            elif 'gdas' in file_format:
                dump = 'gdas'
            hpss_dir = model_hpssdir_list[index]
            link_model_data_dir = os.path.join(cwd, 'data', name)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
                os.makedirs(
                    os.path.join(link_model_data_dir+'/HPSS_jobs')
                )
            for time in time_info:
                valid_time = time['validtime']
                init_time = time['inittime']
                lead = time['lead']
                if init_time.strftime('%H') in ['03', '09', '15', '21']:
                    continue
                else:
                    link_model_forecast_file = os.path.join(
                        link_model_data_dir,
                        'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                    )
                    if not os.path.exists(link_model_forecast_file):
                        model_forecast_filename = format_filler(file_format,
                                                                valid_time, 
                                                                init_time, 
                                                                lead)
                        model_forecast_file = os.path.join(
                            dir, name, model_forecast_filename
                        )
                        if os.path.exists(model_forecast_file):
                            if any(
                                g in model_forecast_file \
                                for g in grib2_file_names
                            ):
                                convert_grib2_grib1(model_forecast_file,
                                                    link_model_forecast_file)
                            else:
                                os.system('ln -sf '+model_forecast_file+' '
                                          +link_model_forecast_file)
                        else:
                            if model_data_run_hpss == 'YES':
                                print("Did not find "
                                      +model_forecast_file+" online..."
                                      +"going to try to get file from HPSS")
                                hpss_tar, hpss_file, hpss_job_filename = (
                                    set_up_gfs_hpss_info(init_time, hpss_dir, 
                                                         dump,
                                                         'f'+lead.zfill(3), 
                                                         link_model_data_dir)
                                )
                                get_hpss_data(hpss_job_filename,
                                              link_model_data_dir, 
                                              link_model_forecast_file,
                                              hpss_tar, hpss_file)
                        if not os.path.exists(link_model_forecast_file):
                            if model_data_run_hpss == 'YES':
                                print("WARNING: "+model_forecast_file+" does "
                                      +"not exist and did not find HPSS file "
                                      +hpss_file+" from "+hpss_tar+" "
                                      +" or walltime exceeded")
                            else:
                                print("WARNING: "+model_forecast_file+" "
                                      +"does not exist")
        # Get truth prepbufr files
        valid_time_list = []
        for time in time_info:
            valid_time = time['validtime']
            if valid_time not in valid_time_list:
                valid_time_list.append(valid_time)
        for valid_time in valid_time_list:
            prepbufr_files_to_check = []
            YYYYmmddHH = valid_time.strftime('%Y%m%d%H')
            YYYYmmdd = valid_time.strftime('%Y%m%d')
            YYYYmm = valid_time.strftime('%Y%m')
            YYYY = valid_time.strftime('%Y')
            mm = valid_time.strftime('%m')
            dd = valid_time.strftime('%d')
            HH = valid_time.strftime('%H')
            if type == 'upper_air':
                link_prepbufr_data_dir = os.path.join(cwd, 'data',
                                                      'prepbufr')
                link_prepbufr_file = os.path.join(link_prepbufr_data_dir,
                                                  'prepbufr.gdas.'+YYYYmmddHH)
                prod_file = os.path.join(prepbufr_prod_upper_air_dir, 
                                         'gdas.'+YYYYmmdd, HH,
                                         'gdas.t'+HH+'z.prepbufr')
                arch_file = os.path.join(prepbufr_arch_dir, 'gdas',
                                         'prepbufr.gdas.'+YYYYmmddHH)
                hpss_date_dir = os.path.join(hpss_prod_base_dir,
                                             'rh'+YYYY, YYYYmm,
                                             YYYYmmdd)
                if int(YYYYmmdd) >= 20200226:
                    hpss_tar_file = (
                        'com_gfs_prod_gdas.'
                        +YYYYmmdd+'_'+HH+'.gdas.tar'
                    )
                    hpss_file = (
                        'gdas.'+YYYYmmdd+'/'+HH+'/gdas.t'+HH+'z.prepbufr'
                    )
                elif int(YYYYmmdd) >= 20190612 and int(YYYYmmdd) < 20200226:
                    hpss_tar_file = (
                        'gpfs_dell1_nco_ops_com_gfs_prod_gdas.'
                        +YYYYmmdd+'_'+HH+'.gdas.tar'
                    )
                    hpss_file = (
                        'gdas.'+YYYYmmdd+'/'+HH+'/gdas.t'+HH+'z.prepbufr'
                    )
                elif int(YYYYmmdd) >= 20170720 and int(YYYYmmdd) < 20190612:
                    hpss_tar_file = (
                        'gpfs_hps_nco_ops_com_gfs_prod_gdas.'
                        +YYYYmmddHH+'.tar'
                    )
                    hpss_file = 'gdas.t'+HH+'z.prepbufr'
                elif int(YYYYmmdd) >= 20160510 and int(YYYYmmdd) < 20170720:
                    hpss_tar_file = 'com2_gfs_prod_gdas.'+YYYYmmddHH+'.tar'
                    hpss_file = 'gdas1.t'+HH+'z.prepbufr'
                else:
                    hpss_tar_file = 'com_gfs_prod_gdas.'+YYYYmmddHH+'.tar'
                    hpss_file = 'gdas1.t'+HH+'z.prepbufr'
                hpss_tar = os.path.join(hpss_date_dir, hpss_tar_file)
                # Make sure using non restricted data for Orion
                if machine == 'ORION':
                    prod_file = prod_file+'.nr'
                    arch_file = arch_file+'.nr'
                    hpss_file = hpss_file+'.nr'
                pbo = {}
                pbo['prodfile'] = prod_file
                pbo['archfile'] = arch_file
                pbo['hpsstar'] = hpss_tar
                pbo['hpssfile'] = hpss_file
                pbo['filetype'] = 'gdas'
                prepbufr_files_to_check.append(pbo)
            elif type == 'conus_sfc':
               if int(YYYYmmdd) > 20170319:
                   link_prepbufr_data_dir = os.path.join(cwd, 'data',
                                                         'prepbufr')
                   link_prepbufr_file = os.path.join(link_prepbufr_data_dir,
                                                     'prepbufr.nam.'
                                                     +YYYYmmddHH)
                   offset_hr = str(int(HH)%6).zfill(2)
                   offset_time = (
                       valid_time 
                       + datetime.timedelta(hours=int(offset_hr))
                   )
                   offset_YYYYmmddHH = offset_time.strftime('%Y%m%d%H')
                   offset_YYYYmmdd = offset_time.strftime('%Y%m%d')
                   offset_YYYYmm = offset_time.strftime('%Y%m')
                   offset_YYYY = offset_time.strftime('%Y')
                   offset_mm = offset_time.strftime('%m')
                   offset_dd = offset_time.strftime('%d')
                   offset_HH = offset_time.strftime('%H')
                   prod_file = os.path.join(prepbufr_prod_conus_sfc_dir,
                                            'nam.'+offset_YYYYmmdd,
                                            'nam.t'+offset_HH
                                            +'z.prepbufr.tm'+offset_hr)
                   arch_file = os.path.join(prepbufr_arch_dir, 'nam',
                                            'nam.'+offset_YYYYmmdd,
                                            'nam.t'+offset_HH+'z.prepbufr.tm'
                                            +offset_hr)
                   hpss_date_dir = os.path.join(hpss_prod_base_dir,
                                                'rh'+offset_YYYY,
                                                offset_YYYYmm,
                                                offset_YYYYmmdd)
                   if int(offset_YYYYmmdd) >= 20200227:
                       hpss_tar_file = (
                           'com_nam_prod_nam.'
                           +offset_YYYYmmddHH+'.bufr.tar'
                       )
                       hpss_file = 'nam.t'+offset_HH+'z.prepbufr.tm'+offset_hr
                   elif (int(offset_YYYYmmdd) >= 20190820
                           and int(offset_YYYYmmdd) < 20200227):
                       hpss_tar_file = (
                           'gpfs_dell1_nco_ops_com_nam_prod_nam.'
                           +offset_YYYYmmddHH+'.bufr.tar'
                       )
                       hpss_file = 'nam.t'+offset_HH+'z.prepbufr.tm'+offset_hr
                   elif int(offset_YYYYmmdd) == 20170320:
                       hpss_tar_file = (
                           'com_nam_prod_nam.'+offset_YYYYmmddHH+'.bufr.tar'
                       )
                       hpss_file = 'nam.t'+offset_HH+'z.prepbufr.tm'+offset_hr
                   else:
                       hpss_tar_file = (
                           'com2_nam_prod_nam.'+offset_YYYYmmddHH+'.bufr.tar'
                       )
                       hpss_file = 'nam.t'+offset_HH+'z.prepbufr.tm'+offset_hr
                   hpss_tar = os.path.join(hpss_date_dir, hpss_tar_file)
                   # Make sure using non restricted data for Orion
                   if machine == 'ORION':
                       prod_file = prod_file+'.nr'
                       arch_file = arch_file+'.nr'
                       hpss_file = hpss_file+'.nr'
                   pbo = {}
                   pbo['prodfile'] = prod_file
                   pbo['archfile'] = arch_file
                   pbo['hpsstar'] = hpss_tar
                   pbo['hpssfile'] = hpss_file
                   pbo['filetype'] = 'nam'
                   prepbufr_files_to_check.append(pbo)
               else:
                   link_prepbufr_data_dir = os.path.join(cwd, 'data',
                                                         'prepbufr')
                   link_prepbufr_file = os.path.join(link_prepbufr_data_dir,
                                                     'prepbufr.ndas.'
                                                     +YYYYmmddHH)
                   ndas_prepbufr_dict = {}
                   for xhr in ['00', '03', '06', '09','12', '15', '18', '21']:
                       xdate = valid_time + datetime.timedelta(hours=int(xhr))
                       ndas_prepbufr_dict['YYYY'+xhr] = xdate.strftime('%Y')
                       ndas_prepbufr_dict['YYYYmm'+xhr] = (
                           xdate.strftime('%Y%m')
                       )
                       ndas_prepbufr_dict['YYYYmmdd'+xhr] = (
                           xdate.strftime('%Y%m%d')
                       )
                       ndas_prepbufr_dict['HH'+xhr] = xdate.strftime('%H')
                   if ndas_prepbufr_dict['HH00'] in ['00', '06', '12', '18']:
                       prod_file1 = os.path.join(
                           prepbufr_prod_conus_sfc_dir,
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd12'],
                           'ndas.t'+ndas_prepbufr_dict['HH12']
                           +'z.prepbufr.tm12'
                       )
                       prod_file2 = os.path.join(
                           prepbufr_prod_conus_sfc_dir,
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd06'],
                           'ndas.t'+ndas_prepbufr_dict['HH06']
                           +'z.prepbufr.tm06'
                       )
                       prod_file3 = os.path.join(
                           prepbufr_prod_conus_sfc_dir,
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd00'],
                           'nam.t'+ndas_prepbufr_dict['HH00']
                           +'z.prepbufr.tm00'
                       )
                       arch_file1 = os.path.join(
                           prepbufr_arch_dir, 'ndas',
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd12'],
                           'ndas.t'+ndas_prepbufr_dict['HH12']
                           +'z.prepbufr.tm12'
                       )
                       arch_file2 = os.path.join(
                           prepbufr_arch_dir, 'ndas',
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd06'],
                           'ndas.t'+ndas_prepbufr_dict['HH06']
                           +'z.prepbufr.tm06'
                       )
                       arch_file3 = os.path.join(
                           prepbufr_arch_dir, 'ndas',
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd00'],
                           'nam.t'+ndas_prepbufr_dict['HH00']
                           +'z.prepbufr.tm00'
                       )
                       hpss_tar1 = os.path.join(
                           hpss_prod_base_dir,
                           'rh'+ndas_prepbufr_dict['YYYY12'],
                           ndas_prepbufr_dict['YYYYmm12'], 
                           ndas_prepbufr_dict['YYYYmmdd12'],
                           'com_nam_prod_ndas.'
                           +ndas_prepbufr_dict['YYYYmmdd12']
                           +ndas_prepbufr_dict['HH12']+'.bufr.tar'
                       )
                       hpss_tar2 = os.path.join(
                           hpss_prod_base_dir,
                           'rh'+ndas_prepbufr_dict['YYYY06'],
                           ndas_prepbufr_dict['YYYYmm06'],
                           ndas_prepbufr_dict['YYYYmmdd06'],
                           'com_nam_prod_ndas.'
                           +ndas_prepbufr_dict['YYYYmmdd06']
                           +ndas_prepbufr_dict['HH06']+'.bufr.tar'
                       )
                       hpss_tar3 = os.path.join(
                           hpss_prod_base_dir,
                           'rh'+ndas_prepbufr_dict['YYYY00'],
                           ndas_prepbufr_dict['YYYYmm00'],
                           ndas_prepbufr_dict['YYYYmmdd00'],
                           'com_nam_prod_nam.'
                           +ndas_prepbufr_dict['YYYYmmdd00']
                           +ndas_prepbufr_dict['HH00']+'.bufr.tar'
                       )
                       hpss_file1 = (
                           'ndas.t'+ndas_prepbufr_dict['HH12']
                           +'z.prepbufr.tm12'
                       )
                       hpss_file2 = (
                           'ndas.t'+ndas_prepbufr_dict['HH06']
                           +'z.prepbufr.tm06'
                       )
                       hpss_file3 = (
                           'nam.t'+ndas_prepbufr_dict['HH00']
                           +'z.prepbufr.tm00'
                       )
                       # Make sure using non restricted data for Orion
                       if machine == 'ORION':
                           prod_file1 = prod_file1+'.nr'
                           arch_file1 = arch_file1+'.nr'
                           hpss_file1 = hpss_file1+'.nr'
                           prod_file2 = prod_file2+'.nr'
                           arch_file2 = arch_file2+'.nr'
                           hpss_file2 = hpss_file2+'.nr'
                           prod_file3 = prod_file3+'.nr'
                           arch_file3 = arch_file3+'.nr'
                           hpss_file3 = hpss_file3+'.nr'
                       pbo1 = {}
                       pbo1['prodfile'] = prod_file1
                       pbo1['archfile'] = arch_file1
                       pbo1['hpsstar'] = hpss_tar1
                       pbo1['hpssfile'] = hpss_file1
                       pbo1['filetype'] = 'ndas'
                       prepbufr_files_to_check.append(pbo1)
                       pbo2 = {}
                       pbo2['prodfile'] = prod_file2
                       pbo2['archfile'] = arch_file2
                       pbo2['hpsstar'] = hpss_tar2
                       pbo2['hpssfile'] = hpss_file2
                       pbo2['filetype'] = 'ndas'
                       prepbufr_files_to_check.append(pbo2)
                       pbo3 = {}
                       pbo3['prodfile'] = prod_file3
                       pbo3['archfile'] = arch_file3
                       pbo3['hpsstar'] = hpss_tar3
                       pbo3['hpssfile'] = hpss_file3
                       pbo3['filetype'] = 'nam'
                       prepbufr_files_to_check.append(pbo3)
                   elif ndas_prepbufr_dict['HH00'] in ['03', '09', '15', '21']:
                       prod_file1 = os.path.join(
                           prepbufr_prod_conus_sfc_dir,
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd09'],
                           'ndas.t'+ndas_prepbufr_dict['HH09']
                           +'z.prepbufr.tm09'
                       )
                       prod_file2 = os.path.join(
                           prepbufr_prod_conus_sfc_dir,
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd03'],
                           'ndas.t'+ndas_prepbufr_dict['HH03']
                           +'z.prepbufr.tm03'
                       )
                       arch_file1 = os.path.join(
                           prepbufr_arch_dir, 'ndas',
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd09'],
                           'ndas.t'+ndas_prepbufr_dict['HH09']
                           +'z.prepbufr.tm09'
                       )
                       arch_file2 = os.path.join(
                           prepbufr_arch_dir, 'ndas',
                           'ndas.'+ndas_prepbufr_dict['YYYYmmdd03'],
                           'ndas.t'+ndas_prepbufr_dict['HH03']
                           +'z.prepbufr.tm03'
                       )
                       hpss_tar1 = os.path.join(
                           hpss_prod_base_dir,
                           'rh'+ndas_prepbufr_dict['YYYY09'],
                           ndas_prepbufr_dict['YYYYmm09'],
                           ndas_prepbufr_dict['YYYYmmdd09'],
                           'com_nam_prod_ndas.'
                           +ndas_prepbufr_dict['YYYYmmdd09']
                           +ndas_prepbufr_dict['HH09']+'.bufr.tar'
                       )
                       hpss_tar2 = os.path.join(
                           hpss_prod_base_dir,
                           'rh'+ndas_prepbufr_dict['YYYY03'],
                           ndas_prepbufr_dict['YYYYmm03'],
                           ndas_prepbufr_dict['YYYYmmdd03'],
                           'com_nam_prod_ndas.'
                           +ndas_prepbufr_dict['YYYYmmdd03']
                           +ndas_prepbufr_dict['HH03']+'.bufr.tar'
                       )
                       hpss_file1 = (
                           'ndas.t'+ndas_prepbufr_dict['HH09']
                           +'z.prepbufr.tm09'
                       )
                       hpss_file2 = (
                           'ndas.t'+ndas_prepbufr_dict['HH03']
                           +'z.prepbufr.tm03'
                       )
                       # Make sure using non restricted data for Orion
                       if machine == 'ORION':
                           prod_file1 = prod_file1+'.nr'
                           arch_file1 = arch_file1+'.nr'
                           hpss_file1 = hpss_file1+'.nr'
                           prod_file2 = prod_file2+'.nr'
                           arch_file2 = arch_file2+'.nr'
                           hpss_file2 = hpss_file2+'.nr'
                       pbo1 = {}
                       pbo1['prodfile'] = prod_file1
                       pbo1['archfile'] = arch_file1
                       pbo1['hpsstar'] = hpss_tar1
                       pbo1['hpssfile'] = hpss_file1
                       pbo1['filetype'] = 'ndas'
                       prepbufr_files_to_check.append(pbo1)
                       pbo2 = {}
                       pbo2['prodfile'] = prod_file2
                       pbo2['archfile'] = arch_file2
                       pbo2['hpsstar'] = hpss_tar2
                       pbo2['hpssfile'] = hpss_file2
                       pbo2['filetype'] = 'ndas'
                       prepbufr_files_to_check.append(pbo2)
            if not os.path.exists(link_prepbufr_data_dir):
                os.makedirs(link_prepbufr_data_dir)
                os.makedirs(
                    os.path.join(link_prepbufr_data_dir+'/HPSS_jobs')
                )
            if not os.path.exists(link_prepbufr_file):
                for prepbufr_file_group in prepbufr_files_to_check:
                    prod_file = prepbufr_file_group['prodfile']
                    arch_file = prepbufr_file_group['archfile']    
                    hpss_tar = prepbufr_file_group['hpsstar']
                    hpss_file = prepbufr_file_group['hpssfile']
                    file_type = prepbufr_file_group['filetype']
                    if os.path.exists(prod_file):
                        os.system('ln -sf '+prod_file+' '+link_prepbufr_file)
                    elif os.path.exists(arch_file):
                        os.system('ln -sf '+arch_file+' '+link_prepbufr_file)
                    else:
                        if prepbufr_run_hpss == 'YES':
                            print("Did not find "+prod_file+" or "
                                  +arch_file+" online...going to try "
                                  +"to get file from HPSS")
                            hpss_job_filename = os.path.join(
                                  link_prepbufr_data_dir,
                                  'HPSS_jobs', 'HPSS_'
                                  +hpss_tar.rpartition('/')[2]
                                  +'_'+hpss_file.replace('/', '_')+'.sh'
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_prepbufr_data_dir, 
                                          link_prepbufr_file,
                                          hpss_tar, hpss_file)
                    if os.path.exists(link_prepbufr_file):
                        break
            if not os.path.exists(link_prepbufr_file):
                error_dir = os.path.join(link_prepbufr_data_dir)
                error_file = os.path.join(
                    error_dir,
                    'error_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                )
                for prepbufr_file_group in prepbufr_files_to_check:
                    prod_file = prepbufr_file_group['prodfile']
                    arch_file = prepbufr_file_group['archfile']
                    hpss_tar = prepbufr_file_group['hpsstar']
                    hpss_file = prepbufr_file_group['hpssfile']
                    file_type = prepbufr_file_group['filetype']
                    if prepbufr_run_hpss == 'YES':
                        error_msg = ('WARNING: '+prod_file+' and '+arch_file
                                     +' do not exist and did not find '
                                     +'HPSS file '+hpss_file+' from '
                                     +hpss_tar+' or walltime exceeded')
                    else:
                        error_msg = ('WARNING: '+prod_file+' and '
                                     +arch_file+' do not exist')
                    print(error_msg)
                    with open(error_file, 'a') as file:
                        file.write(error_msg)
elif RUN == 'grid2obs_step2':
    # Read in environment variables
    type_list = os.environ['g2o2_type_list'].split(' ')
    gather_by_list = os.environ['g2o2_gather_by_list'].split(' ')
    for type in type_list:
        fhr_list_type = os.environ['g2o2_fhr_list_'+type].split(', ')
        if plot_by == 'VALID':
            start_hr_type = os.environ['g2o2_valid_hr_beg_'+type]
            end_hr_type = os.environ['g2o2_valid_hr_end_'+type]
            hr_inc_type = os.environ['g2o2_valid_hr_inc_'+type]
        else:
            start_hr_type = os.environ['g2o2_init_hr_beg']
            end_hr_type = os.environ['g2o2_init_hr_end']
            hr_inc_type = os.environ['g2o2_init_hr_inc']
        # Get date and time information
        time_info = get_time_info(start_date, end_date, start_hr_type,
                                  end_hr_type, hr_inc_type, fhr_list_type,
                                  plot_by)
        # Get archive MET .stat files
        cwd = os.getcwd()
        for name in model_list:
            index = model_list.index(name)
            if len(model_arch_dir_list) != len(model_list):
                arch_dir = model_arch_dir_list[0]
            else:
                arch_dir = model_arch_dir_list[index]
            if len(gather_by_list) != len(model_list):
                gather_by = gather_by_list[0]
            else:
                gather_by = gather_by_list[index]
            full_arch_dir = os.path.join(arch_dir, 'metplus_data',
                                         'by_'+gather_by, 'grid2obs',
                                          type)
            link_model_data_dir = os.path.join(cwd, 'data', name, type)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
            for time in time_info:
                valid_time = time['validtime']
                init_time = time['inittime']
                lead = time['lead']
                if gather_by == 'VALID':
                    stat_file = os.path.join(full_arch_dir,
                                             valid_time.strftime('%H')+'Z',
                                             name, name+'_'
                                             +valid_time.strftime('%Y%m%d')
                                             +'.stat')
                    link_stat_file = os.path.join(link_model_data_dir, name
                                                  +'_valid'+valid_time \
                                                  .strftime('%Y%m%d')
                                                  +'_valid'+valid_time \
                                                  .strftime('%H')+'.stat')
                elif gather_by == 'INIT':
                    if (init_time.strftime('%H') not in 
                            [ '03', '09', '15', '21' ]):
                        stat_file = os.path.join(full_arch_dir,
                                                 init_time.strftime('%H')+'Z',
                                                 name, name+'_'
                                                 +init_time.strftime('%Y%m%d')
                                                 +'.stat')
                        link_stat_file = os.path.join(link_model_data_dir,
                                                      name+'_init'+init_time \
                                                      .strftime('%Y%m%d')
                                                      +'_init'+init_time \
                                                      .strftime('%H')+'.stat')
                elif gather_by == 'VSDB':
                    if (init_time.strftime('%H') not in 
                            [ '03', '09', '15', '21' ]):
                        stat_file = os.path.join(full_arch_dir,
                                                 init_time.strftime('%H')+'Z',
                                                 name, name+'_'
                                                 +valid_time.strftime('%Y%m%d')
                                                 +'.stat')
                        link_stat_file = os.path.join(link_model_data_dir,
                                                      name+'_valid'
                                                      +valid_time \
                                                      .strftime('%Y%m%d')
                                                      +'_init'+init_time \
                                                      .strftime('%H')+'.stat')
                if not os.path.exists(link_stat_file):
                    if os.path.exists(stat_file):
                        os.system('ln -sf '+stat_file+' '
                                  +link_stat_file)
                    else:
                        print("WARNING: "+stat_file+" "
                              +"does not exist")
elif RUN == 'precip_step1':
    # Read in environment variables
    obtype = os.environ['precip1_obtype']
    accum_length = int(os.environ['precip1_accum_length'])
    model_bucket_list = os.environ['precip1_model_bucket_list'].split(' ')
    model_var_name_list = os.environ['precip1_model_varname_list'].split(' ')
    obs_run_hpss = os.environ['precip1_obs_data_runhpss']
    if machine == 'ORION':
        print("WARNING: Orion does not currently have access to HPSS..."
              +"setting precip1_obs_data_runhpss to NO")
        obs_run_hpss = 'NO'
    if make_met_data_by == 'VALID':
        start_hr = os.environ['precip1_valid_hr_beg']
        end_hr = os.environ['precip1_valid_hr_end']
        hr_inc = os.environ['precip1_valid_hr_inc']
    else:
        start_hr = os.environ['prceip1_init_hr_beg']
        end_hr = os.environ['precip1_init_hr_end']
        hr_inc = os.environ['precip1_init_hr_inc']
    fhr_list = os.environ['precip1_fhr_list'].split(', ')
    # Get date and time information 
    sdate = datetime.datetime(int(start_date[0:4]), int(start_date[4:6]),
                              int(start_date[6:]), int(start_hr))
    edate = datetime.datetime(int(end_date[0:4]), int(end_date[4:6]),
                              int(end_date[6:]), int(end_hr))
    date_inc = datetime.timedelta(seconds=int(hr_inc))
    time_info = get_time_info(start_date, end_date,
                              start_hr, end_hr, hr_inc,
                              fhr_list, make_met_data_by)
    # Get model forecast files
    cwd = os.getcwd()
    for name in model_list:
        index = model_list.index(name)
        dir = model_dir_list[index]
        file_format = model_fileformat_list[index]
        if 'gfs' in file_format:
            dump = 'gfs'
        elif 'gdas' in file_format:
            dump = 'gdas'
        hpss_dir = model_hpssdir_list[index]
        bucket = int(model_bucket_list[index])
        var_name = model_var_name_list[index]
        nfiles_accum = accum_length/bucket
        file_accum_intvl = bucket
        link_model_data_dir = os.path.join(cwd, 'data', name)
        if not os.path.exists(link_model_data_dir):
            os.makedirs(link_model_data_dir)
            os.makedirs(
                os.path.join(link_model_data_dir, 'HPSS_jobs')
            )
        for time in time_info:
            valid_time = time['validtime']
            init_time = time['inittime']
            lead_end = time['lead']
            if init_time.strftime('%H') in ['03', '09', '15', '21']:
                continue
            else:
                nf, leads_in_accum_list = 1, []
                while nf <= nfiles_accum:
                    lead_now = int(lead_end)-((nf-1)*file_accum_intvl)
                    leads_in_accum_list.append(lead_now)
                    nf+=1
                leads_in_accum_list_check = filter(lambda x: x > 0,
                                                   leads_in_accum_list)
                if len(leads_in_accum_list_check) == len(leads_in_accum_list):
                    for lead_in_accum in leads_in_accum_list:
                        lead = str(lead_in_accum).zfill(2)
                        link_model_forecast_file = os.path.join(
                            link_model_data_dir,
                            'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                        )
                        if not os.path.exists(link_model_forecast_file):
                            model_forecast_filename = format_filler(
                                file_format, valid_time, init_time, lead
                            )
                            model_forecast_file = os.path.join(
                                dir, name, model_forecast_filename
                            )
                            if os.path.exists(model_forecast_file):
                                if var_name == 'APCP':
                                    if any(
                                        g in model_forecast_file \
                                        for g in grib2_file_names
                                    ):
                                        convert_grib2_grib1(
                                            model_forecast_file,
                                            link_model_forecast_file
                                        )
                                    else:
                                        os.system('ln -sf '
                                                  +model_forecast_file+' '
                                                  +link_model_forecast_file)
                                elif var_name == 'PRATE':
                                    if any(
                                        g in model_forecast_file \
                                        for g in grib2_file_names
                                    ):
                                        convert_grib2_grib1(
                                            model_forecast_file,
                                            link_model_forecast_file
                                        )
                                    else:
                                        os.system('cp '
                                                  +model_forecast_file+' '
                                                  +link_model_forecast_file)
                            else:
                                if model_data_run_hpss == 'YES':
                                    print("Did not find "
                                          +model_forecast_file+" online..."
                                          +"going to try to get file "
                                          +"from HPSS")
                                    hpss_tar, hpss_file, hpss_job_filename = (
                                        set_up_gfs_hpss_info(
                                            init_time, hpss_dir,
                                            dump, 
                                            'f'+lead.zfill(3),
                                            link_model_data_dir
                                        )
                                    )
                                    get_hpss_data(hpss_job_filename,
                                                  link_model_data_dir, 
                                                  link_model_forecast_file,
                                                  hpss_tar, hpss_file)
                            if not os.path.exists(link_model_forecast_file):
                                if model_data_run_hpss == 'YES':
                                    print("WARNING: "+model_forecast_file+" "
                                          +"does not exist and did not find "
                                          +"HPSS file "+hpss_file+" from "
                                          +hpss_tar+" or walltime exceeded")
                                else:
                                    print("WARNING: "+model_forecast_file+" "
                                          +"does not exist")
                            else:
                                if var_name == 'PRATE':
                                    os.system('mv '
                                              +link_model_forecast_file+' '
                                              +link_model_data_dir+'/tmp_gb1')
                                    cnvgrib = os.environ['CNVGRIB']
                                    os.system(cnvgrib+' -g12 '
                                              +link_model_data_dir+'/tmp_gb1 '
                                              +link_model_data_dir+'/tmp_gb2')
                                    wgrib2 = os.environ['WGRIB2']
                                    os.system(wgrib2+' '
                                              +link_model_data_dir+'/tmp_gb2 '
                                              +'-match ":PRATE:" '
                                              +'-rpn "3600:*" -set_var APCP '
                                              +'-set table_4.10 1 -grib_out '
                                              +link_model_data_dir
                                              +'/tmp_gb2_APCP >>/dev/null')
                                    os.system(cnvgrib+' -g21 '
                                              +link_model_data_dir
                                              +'/tmp_gb2_APCP '
                                              +link_model_forecast_file)
                                    os.system('rm '+link_model_data_dir
                                              +'/tmp*')
    # Get preipitation analysis truth
    valid_time_list = []
    for time in time_info:
        valid_time = time['validtime']
        if valid_time not in valid_time_list:
            valid_time_list.append(valid_time)
    for valid_time in valid_time_list:
        YYYYmmddHH = valid_time.strftime('%Y%m%d%H')
        YYYYmmdd = valid_time.strftime('%Y%m%d')
        YYYYmm = valid_time.strftime('%Y%m')
        YYYY = valid_time.strftime('%Y')
        mm = valid_time.strftime('%m')
        dd = valid_time.strftime('%d')
        HH = valid_time.strftime('%H')
        link_obs_data_dir = os.path.join(cwd, 'data',
                                         obtype)
        if obtype == 'ccpa' and accum_length == 24:
            link_obs_file = os.path.join(link_obs_data_dir,
                                         'ccpa.'+YYYYmmdd+'12.24h') 
            prod_dir = os.environ['ccpa_24hr_prod_dir']
            prod_file = os.path.join(prod_dir,
                                     'precip.'+YYYYmmdd,
                                     'ccpa.'+YYYYmmdd+'12.24h')
            arch_dir = os.environ['ccpa_24hr_arch_dir']
            arch_file = os.path.join(arch_dir,
                                     'ccpa.'+YYYYmmdd+'12.24h')
            hpss_date_dir = os.path.join(hpss_prod_base_dir,
                                         'rh'+YYYY, YYYYmm,
                                         YYYYmmdd)
            if int(YYYYmmdd) >= 20200226:
                hpss_tar = os.path.join(hpss_date_dir,
                                        'com_'
                                         +'verf_prod_precip'
                                         +YYYYmmdd+'.precip.tar')
            elif int(YYYYmmdd) >= 20200126 and int(YYYYmmdd) < 20200226:
                hpss_tar = os.path.join(hpss_date_dir,
                                        'gpfs_dell1_nco_ops_com_'
                                        +'verf_prod_precip'
                                        +YYYYmmdd+'.precip.tar')
            else:
                hpss_tar = os.path.join(hpss_date_dir,
                                        'com_verf_prod_precip.'
                                        +YYYYmmdd+'.precip.tar')
            hpss_file = 'ccpa.'+YYYYmmdd+'12.24h'
        else:
            print("ERROR: "+obtype+" for observations with "
                  +"accumulation length of "+str(accum_length)
                  +"hr is not valid")
            exit(1)
        if not os.path.exists(link_obs_data_dir):
            os.makedirs(link_obs_data_dir)
            os.makedirs(
                os.path.join(link_obs_data_dir+'/HPSS_jobs')
            )
        if not os.path.exists(link_obs_file):
            if os.path.exists(prod_file):
                os.system('ln -sf '+prod_file+' '+link_obs_file)
            elif os.path.exists(arch_file):
                os.system('ln -sf '+arch_file+' '+link_obs_file)
            else:
                if obs_run_hpss == 'YES':
                    print("Did not find "+prod_file+" or "+arch_file+" "
                          +"online...going to try to get file from HPSS")
                    hpss_job_filename = os.path.join(
                        link_obs_data_dir, 'HPSS_jobs', 
                        'HPSS_'+hpss_tar.rpartition('/')[2]
                        +'_'+hpss_file.replace('/', '_')+'.sh'
                    )
                    get_hpss_data(hpss_job_filename,
                                  link_obs_data_dir, link_obs_file,
                                  hpss_tar, hpss_file)
        if not os.path.exists(link_obs_file):
            error_dir = os.path.join(link_obs_data_dir)
            error_file = os.path.join(
                error_dir,
                'error_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
            )
            if obs_run_hpss == 'YES':
                error_msg = ('WARNING: '+prod_file+' and '+arch_file+' do not '
                             +'exist and did not find HPSS file '
                             +hpss_file+' from '+hpss_tar+' or '
                             +'walltime exceeded')
            else:
                error_msg = ('WARNING: '+prod_file+' and '
                             +arch_file+' do not exist')
            print(error_msg)
            with open(error_file, 'a') as file:
                file.write(error_msg)
elif RUN == 'precip_step2':
    # Read in environment variables
    #obtype = os.environ['precip2_obtype']
    #accum_length = int(os.environ['precip2_accum_length'])
    type_list = os.environ['precip2_type_list'].split(' ')
    gather_by_list = os.environ['precip2_gather_by_list'].split(' ')
    if plot_by == 'VALID':
        start_hr = os.environ['precip2_valid_hr_beg']
        end_hr = os.environ['precip2_valid_hr_end']
        hr_inc = os.environ['precip2_valid_hr_inc']
    else:
        start_hr = os.environ['precip2_init_hr_beg']
        end_hr = os.environ['precip2_init_hr_end']
        hr_inc = os.environ['precip2_init_hr_inc']
    fhr_list = os.environ['precip2_fhr_list'].split(', ')
    # Get date and time information
    time_info = get_time_info(start_date, end_date,
                              start_hr, end_hr, hr_inc,
                              fhr_list, plot_by)
    # Get archive MET .stat files
    cwd = os.getcwd()
    for name in model_list:
        index = model_list.index(name)
        if len(model_arch_dir_list) != len(model_list):
            arch_dir = model_arch_dir_list[0]
        else:
            arch_dir = model_arch_dir_list[index]
        if len(gather_by_list) != len(model_list):
            gather_by = gather_by_list[0]
        else:
            gather_by = gather_by_list[index]
        for type in type_list:
            full_arch_dir = os.path.join(arch_dir, 'metplus_data',
                                         'by_'+gather_by, 'precip',
                                          type)
            link_model_data_dir = os.path.join(cwd, 'data', name, type)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
            for time in time_info:
                valid_time = time['validtime']
                init_time = time['inittime']
                lead = time['lead']
                if gather_by == 'VALID':
                    stat_file = os.path.join(full_arch_dir,
                                             valid_time.strftime('%H')+'Z',
                                             name, name+'_'
                                             +valid_time.strftime('%Y%m%d')
                                             +'.stat')
                    link_stat_file = os.path.join(link_model_data_dir, name
                                                  +'_valid'+valid_time \
                                                  .strftime('%Y%m%d')
                                                  +'_valid'+valid_time \
                                                  .strftime('%H')+'.stat')
                elif gather_by == 'INIT':
                    if (init_time.strftime('%H') not in
                            ['03', '09', '15', '21']):
                        stat_file = os.path.join(full_arch_dir,
                                                 init_time.strftime('%H')+'Z',
                                                 name, name+'_'
                                                 +init_time.strftime('%Y%m%d')
                                                 +'.stat')
                        link_stat_file = os.path.join(link_model_data_dir,
                                                      name+'_init'+init_time \
                                                      .strftime('%Y%m%d')
                                                      +'_init'+init_time \
                                                      .strftime('%H')+'.stat')

                elif gather_by == 'VSDB':
                    if (init_time.strftime('%H') not in
                            ['03', '09', '15', '21']):
                        stat_file = os.path.join(full_arch_dir,
                                                 init_time.strftime('%H')+'Z',
                                                 name, name+'_'
                                                 +valid_time.strftime('%Y%m%d')
                                                 +'.stat')
                        link_stat_file = os.path.join(link_model_data_dir,
                                                      name+'_valid'
                                                      +valid_time \
                                                      .strftime('%Y%m%d')
                                                      +'_init'+init_time \
                                                      .strftime('%H')+'.stat')
                if not os.path.exists(link_stat_file):
                    if os.path.exists(stat_file):
                        os.system('ln -sf '+stat_file+' '
                                  +link_stat_file)
                    else:
                        print("WARNING: "+stat_file+" "
                              +"does not exist")
elif RUN == 'tropcyc':
    import get_tc_info
    # Read in environment variables
    model_atcf_name_list = (
        os.environ['tropcyc_model_atcf_name_list'].split(' ')
    )
    model_fileformat_list = (
        os.environ['tropcyc_model_fileformat_list'].split(' ')
    )
    config_storm_list = os.environ['tropcyc_storm_list'].split(' ')
    fhr_list = os.environ['tropcyc_fhr_list'].split(', ')
    nhc_atcfnoaa_bdeck_dir = os.environ['nhc_atcfnoaa_bdeck_dir']
    nhc_atcfnoaa_adeck_dir = os.environ['nhc_atcfnoaa_adeck_dir']
    nhc_atcfnavy_bdeck_dir = os.environ['nhc_atcfnavy_bdeck_dir']
    nhc_atcfnavy_adeck_dir = os.environ['nhc_atcfnavy_adeck_dir']
    nhc_atcf_bdeck_ftp = os.environ['nhc_atcf_bdeck_ftp']
    nhc_atcf_adeck_ftp = os.environ['nhc_atcf_adeck_ftp']
    nhc_atfc_arch_ftp = os.environ['nhc_atfc_arch_ftp']
    navy_atcf_bdeck_ftp = os.environ['navy_atcf_bdeck_ftp']
    trak_arch_dir = os.environ['trak_arch_dir']
    fcyc_list = os.environ['tropcyc_fcyc_list'].split(' ')
    #if make_met_data_by == 'VALID':
    #    start_hr = os.environ['tropcyc_valid_hr_beg']
    #    end_hr = os.environ['tropcyc_valid_hr_end']
    #    hr_inc = os.environ['tropcyc_valid_hr_inc']
    #else:
    #    start_hr = os.environ['tropcyc_init_hr_beg']
    #    end_hr = os.environ['tropcyc_init_hr_end']
    #    hr_inc = os.environ['tropcyc_init_hr_inc']
    #fhr_list = os.environ['tropcyc_fhr_list'].split(', ')
    # Check storm_list to see if all storms for basin and year
    # requested
    storm_list = []
    for storm in config_storm_list:
        basin = storm.split('_')[0]
        year = storm.split('_')[1]
        name = storm.split('_')[2]
        if name == 'ALLNAMED':
            all_storms_in_basin_year_list = (
                get_tc_info.get_all_tc_storms_basin_year(basin, year)
            )
            for byn in all_storms_in_basin_year_list:
                storm_list.append(byn)
        else:
            storm_list.append(storm)
    # Create output directories
    cwd = os.getcwd()
    for mname in model_list:
        index = model_list.index(mname)
        dir = model_dir_list[index]
        file_format = model_fileformat_list[index]
        hpss_dir = model_hpssdir_list[index]
        link_model_data_dir = os.path.join(cwd, 'data', mname)
        if not os.path.exists(link_model_data_dir):
            os.makedirs(link_model_data_dir)
            os.makedirs(
                os.path.join(link_model_data_dir, 'HPSS_jobs')
            )
    # Get bdeck/truth, adeck, and model track files
    link_bdeck_data_dir = os.path.join(cwd, 'data', 'bdeck')
    if not os.path.exists(link_bdeck_data_dir):
        os.makedirs(link_bdeck_data_dir)
    link_adeck_data_dir = os.path.join(cwd, 'data', 'adeck')
    if not os.path.exists(link_adeck_data_dir):
        os.makedirs(link_adeck_data_dir)
    for storm in storm_list:
        basin = storm.split('_')[0]
        year = storm.split('_')[1]
        name = storm.split('_')[2]
        storm_id =  get_tc_info.get_tc_storm_id(storm)
        # Get bdeck files
        bdeck_filename = 'b'+storm_id+'.dat'
        link_bdeck_file = os.path.join(link_bdeck_data_dir, bdeck_filename)
        if basin in [ 'AL', 'CP', 'EP']:
            nhc_bdeck_file = os.path.join(nhc_atcfnoaa_bdeck_dir,
                                          bdeck_filename)
            trak_arch_bdeck_file = os.path.join(trak_arch_dir, 'btk',
                                                bdeck_filename)
            if os.path.exists(nhc_bdeck_file):
                os.system('ln -sf '+nhc_bdeck_file+' '
                           +link_bdeck_file)
            elif os.path.exists(trak_arch_bdeck_file):
                os.system('ln -sf '+trak_arch_bdeck_file+' '
                           +link_bdeck_file)
            else:
                print("Did not find "+nhc_bdeck_file+" or "
                      +trak_arch_bdeck_file+" online..."
                      +"going to try to get file from NHC ftp")
                if year == '2019':
                    nhc_ftp_bdeck_file = (
                        os.path.join(nhc_atcf_bdeck_ftp, bdeck_filename)
                    )
                    os.system('wget -q '+nhc_ftp_bdeck_file+' -P '
                              +link_bdeck_data_dir)
                else:
                    nhc_ftp_bdeck_gzfile = (
                        os.path.join(nhc_atfc_arch_ftp, year,
                                     bdeck_filename+'.gz')
                    )
                    nhc_bdeck_gzfile = os.path.join(link_bdeck_data_dir,
                                                    bdeck_filename+'.gz')
                    os.system('wget -q '+nhc_ftp_bdeck_gzfile+' -P '
                              +link_bdeck_data_dir)
                    if os.path.exists(nhc_bdeck_gzfile):
                        os.system('gunzip -q -f '+nhc_bdeck_gzfile)
                if not os.path.exists(link_bdeck_file):
                    error_msg = ("WARNING: "+nhc_bdeck_file+" and "
                                 +trak_arch_bdeck_file+" do not exist "
                                 +"and did not find file on NHC ftp site")
        elif basin == 'WP':
            nhc_bdeck_file = os.path.join(nhc_atcfnavy_bdeck_dir,
                                          bdeck_filename)
            trak_arch_bdeck_file = os.path.join(trak_arch_dir, 'btk',
                                                bdeck_filename) 
            if int(year) < 2019:
                print("Getting most up to date "+bdeck_filename+" file "
                      +"from Navy website archive")
                navy_ftp_bdeck_zipfile = (
                        os.path.join(navy_atcf_bdeck_ftp, year, year+'s-bwp',
                                     'bwp'+year+'.zip')
                    )
                navy_bdeck_zipfile = os.path.join(link_bdeck_data_dir,
                                                  'bwp'+year+'.zip')
                if not os.path.exists(navy_bdeck_zipfile):
                    os.system('wget -q '+navy_ftp_bdeck_zipfile+' -P '
                              +link_bdeck_data_dir)
                if os.path.exists(navy_bdeck_zipfile):
                    os.system('unzip -qq -o -d '+link_bdeck_data_dir+' '
                              +navy_bdeck_zipfile+' '+bdeck_filename)
                else:
                    print("Could not retrieve "+bdeck_filename+" from Navy "
                          +"website archive...going to try to find in NHC "
                          +"and HWRF archive")
                    if not os.path.exists(link_bdeck_file):
                        if os.path.exists(nhc_bdeck_file):
                            os.system('ln -sf '+nhc_bdeck_file+' '
                                      +link_bdeck_file)
                        elif os.path.exists(trak_arch_bdeck_file):
                            os.system('ln -sf '+trak_arch_bdeck_file+' '
                                      +link_bdeck_file)
                        else:
                            error_msg = ("WARNING: could not get file from "
                                         +"Navy website archive and "
                                         +nhc_bdeck_file+" and "
                                         +trak_arch_bdeck_file+" do not exist")
            else:
                if os.path.exists(nhc_bdeck_file):
                    os.system('ln -sf '+nhc_bdeck_file+' '
                               +link_bdeck_file)
                elif os.path.exists(trak_arch_bdeck_file):
                    os.system('ln -sf '+trak_arch_bdeck_file+' '
                              +link_bdeck_file)
                else:
                    error_msg = ("WARNING: "+nhc_bdeck_file+" and "
                                 +trak_arch_bdeck_file+" do not exist")
        else:
            print("ERROR: "+basin+" is not currently supported "
                  +"at this time")
            exit(1)
        if not os.path.exists(link_bdeck_file):
            error_dir = os.path.join(link_bdeck_data_dir)
            error_file = os.path.join(
                error_dir,
                'error_b'+storm_id+'.txt'
            )
            print(error_msg)
            with open(error_file, 'a') as file:
                file.write(error_msg)
        # Get adeck files
        adeck_filename = 'a'+storm_id+'.dat'
        link_adeck_file = os.path.join(link_adeck_data_dir, adeck_filename)
        if basin in [ 'AL', 'CP', 'EP']:
            nhc_adeck_file = os.path.join(nhc_atcfnoaa_adeck_dir,
                                          adeck_filename)
            trak_arch_adeck_file = os.path.join(trak_arch_dir, 'aid_nws',
                                                adeck_filename)
            if os.path.exists(nhc_adeck_file):
                os.system('ln -sf '+nhc_adeck_file+' '
                           +link_adeck_file)
            elif os.path.exists(trak_arch_adeck_file):
                os.system('ln -sf '+trak_arch_adeck_file+' '
                           +link_adeck_file)
            else:
                print("Did not find "+nhc_adeck_file+" or "
                      +trak_arch_adeck_file+" online..."
                      +"going to try to get file from NHC ftp")
                nhc_adeck_gzfile = os.path.join(link_adeck_data_dir,
                                                adeck_filename+'.gz')
                if year == '2019':
                    nhc_ftp_adeck_gzfile = (
                        os.path.join(nhc_atcf_adeck_ftp, adeck_filename+'.gz')
                    )
                else:
                    nhc_ftp_adeck_gzfile = (
                        os.path.join(nhc_atfc_arch_ftp, year,
                                     adeck_filename+'.gz')
                    )
                os.system('wget -q '+nhc_ftp_adeck_gzfile+' -P '
                          +link_adeck_data_dir)
                if os.path.exists(nhc_adeck_gzfile):
                    os.system('gunzip -q '+nhc_adeck_gzfile)
                if not os.path.exists(link_adeck_file):
                    print("WARNING: "+nhc_adeck_file+" and "
                          +trak_arch_adeck_file+" do not exist and "
                          +"did not find file on NHC ftp site")
        elif basin == 'WP':
            nhc_adeck_file = os.path.join(nhc_atcfnavy_adeck_dir,
                                          adeck_filename)
            trak_arch_adeck_file = os.path.join(trak_arch_dir, 'aid',
                                                adeck_filename)
            if os.path.exists(nhc_adeck_file):
                os.system('ln -sf '+nhc_adeck_file+' '
                           +link_adeck_file)
            elif os.path.exists(trak_arch_adeck_file):
                os.system('ln -sf '+trak_arch_adeck_file+' '
                           +link_adeck_file)
            else:
                print("WARNING: "+nhc_adeck_file+" and "
                      +trak_arch_adeck_file+" do not exist")
        else:
            print("ERROR: "+basin+" is not currently supported "
                  +"at this time")
            exit(1)
        # Get model track files
        # currently set up to mimic VSDB verification
        # which uses model track data initialized
        # in storm dates
        if os.path.exists(link_bdeck_file):
            storm_start_date, storm_end_date = get_tc_info.get_tc_storm_dates(
                link_bdeck_file
            )
            time_info = get_time_info(
                storm_start_date[0:8], storm_end_date[0:8],
                storm_start_date[-2:], storm_end_date[-2:],
                '21600', fhr_list, 'INIT'
            )
            for mname in model_list:
                index = model_list.index(mname)
                model_atcf_abbrv = model_atcf_name_list[index]
                if mname == 'gfs' and model_atcf_abbrv != 'GFSO':
                    print("Using operational GFS...using ATCF name as GFSO "
                          +"to comply with MET")
                    model_atcf_abbrv = 'GFSO'
                dir = model_dir_list[index]
                file_format = model_fileformat_list[index]
                hpss_dir = model_hpssdir_list[index]
                link_model_data_dir = os.path.join(cwd, 'data', mname)
                for time in time_info:
                    valid_time = time['validtime']
                    init_time = time['inittime']
                    lead = time['lead']
                    if init_time.strftime('%H') in fcyc_list:
                        if init_time.strftime('%H') in ['03', '09',
                                                        '15', '21']:
                            continue
                        else:
                            link_model_track_file = os.path.join(
                                link_model_data_dir,
                                'track.'+init_time.strftime('%Y%m%d%H')+'.dat'
                            )
                            if not os.path.exists(link_model_track_file):
                                model_track_filename = format_filler(
                                    file_format, valid_time, init_time, lead
                                )
                                model_track_file = os.path.join(
                                    dir, mname, model_track_filename
                                )
                                if os.path.exists(model_track_file):
                                    os.system('cp '+model_track_file+' '
                                               +link_model_track_file)
                                else:
                                    if mname == 'gfs':
                                        print("Did not find "
                                              +model_track_file+" online "
                                              +"going to get information "
                                              +"adeck file")
                                        if os.path.exists(link_adeck_file):
                                            ps = subprocess.Popen(
                                                'grep -R "AVNO" '
                                                +link_adeck_file+' | grep "'
                                                +init_time.strftime('%Y%m%d%H')
                                                +'"',
                                                shell=True, 
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT
                                            )
                                            output = ps.communicate()[0]
                                            with open(link_model_track_file,
                                                      'w') as lmtf:
                                                lmtf.write(output)
                                        else:
                                            print("WARNING: "
                                                  +model_track_file+" and "
                                                  +link_adeck_file+" do not "
                                                  +"exist")
                                    else:
                                        if model_data_run_hpss == 'YES':
                                            print("Did not find "
                                                  +model_track_file+" "
                                                  +"online...going to try to "
                                                  +"get file from HPSS")
                                            (hpss_tar, hpss_file,
                                                 hpss_job_filename) = (
                                                set_up_gfs_hpss_info(
                                                    init_time, hpss_dir,
                                                    'gfs',
                                                    'cyclone.trackatcfunix',
                                                    link_model_data_dir
                                                )
                                            )
                                            get_hpss_data(
                                                hpss_job_filename,
                                                link_model_data_dir,
                                                link_model_track_file,
                                                hpss_tar, hpss_file
                                            )
                                        if not os.path.exists(
                                                link_model_track_file
                                        ):
                                            if model_data_run_hpss == 'YES':
                                                print("WARNING: "
                                                      +model_track_file+" "
                                                      +"does not exist and "
                                                      +"did not find HPSS "
                                                      +"file "+hpss_file+" "
                                                      +"from "+hpss_tar+" or "
                                                      +"walltime exceeded")
                                            else:
                                                print("WARNING: "
                                                      +model_track_file+" "
                                                      +"does not exist")
                                if os.path.exists(link_model_track_file):
                                    if mname == 'gfs':
                                        abbrv_to_replace = 'AVNO'
                                    else:
                                        abbrv_to_replace = mname[0:4].upper()
                                    os.system('sed -i s/'+abbrv_to_replace+'/'
                                              +model_atcf_abbrv+'/g '
                                              +link_model_track_file)
elif RUN == 'maps2d':
    # Read in environment variables
    type_list = os.environ['maps2d_type_list'].split(' ')
    make_met_data_by = os.environ['maps2d_make_met_data_by']
    anl_name = os.environ['maps2d_anl_name']
    anl_file_format_list = os.environ['maps2d_anl_fileformat_list'].split(' ')
    start_hr = os.environ['maps2d_hr_beg']
    end_hr = os.environ['maps2d_hr_end']
    hr_inc = os.environ['maps2d_hr_inc']
    fhr_list = os.environ['maps2d_fhr_list'].split(', ')
    forecast_to_plot_list = (
        os.environ['maps2d_forecast_to_plot_list'].split(' ')
    )
    forecast_anl_diff = os.environ['maps2d_model2model_forecast_anl_diff']
    # Get date and time information
    time_info = get_time_info(start_date, end_date, start_hr, end_hr, hr_inc,
                              fhr_list, make_met_data_by)
    # Get model forecast files
    cwd = os.getcwd()
    for name in model_list:
        index = model_list.index(name)
        dir = model_dir_list[index]
        file_format = model_fileformat_list[index]
        if 'gfs' in file_format:
            dump = 'gfs'
        elif 'gdas' in file_format:
            dump = 'gdas'
        hpss_dir = model_hpssdir_list[index]
        link_model_data_dir = os.path.join(cwd, 'data', name)
        if not os.path.exists(link_model_data_dir):
            os.makedirs(link_model_data_dir)
            os.makedirs(
                os.path.join(link_model_data_dir, 'HPSS_jobs')
            )
        for time in time_info:
            valid_time = time['validtime']
            init_time = time['inittime']
            lead = time['lead']
            if init_time.strftime('%H') in ['03', '09', '15', '21']:
                continue
            elif lead == '00' and fhr_list == ['anl']:
                break
            else:
                link_model_forecast_file = os.path.join(
                    link_model_data_dir,
                    'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                )
                if not os.path.exists(link_model_forecast_file):
                    model_forecast_filename = format_filler(file_format,
                                                            valid_time,
                                                            init_time, lead)
                    model_forecast_file = os.path.join(dir, name,
                                                       model_forecast_filename)
                    if os.path.exists(model_forecast_file):
                        if any(
                            g in model_forecast_file for g in grib2_file_names
                        ):
                            convert_grib2_grib1(model_forecast_file,
                                                link_model_forecast_file)
                        else:
                            os.system('ln -sf '+model_forecast_file+' '
                                      +link_model_forecast_file)
                    else:
                        if model_data_run_hpss == 'YES':
                            print("Did not find "+model_forecast_file+" "
                                  +"online...going to try to get file "
                                  +"from HPSS")
                            hpss_tar, hpss_file, hpss_job_filename = (
                                set_up_gfs_hpss_info(init_time, hpss_dir,
                                                     dump,
                                                     'f'+lead.zfill(3),
                                                     link_model_data_dir)
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_model_data_dir,
                                          link_model_forecast_file,
                                          hpss_tar, hpss_file)
                    if not os.path.exists(link_model_forecast_file):
                        if model_data_run_hpss == 'YES':
                            print("WARNING: "+model_forecast_file+" "
                                  +"does not exist and did not find "
                                  +"HPSS file "+hpss_file+" from "
                                  +hpss_tar+" or walltime exceeded")
                        else:
                            print("WARNING: "+model_forecast_file+" "
                                  +"does not exist")
    # Get matching valid time analysis files for model forecasts
    # for model2model comparison to analysis
    if forecast_anl_diff == 'YES':
        valid_time_list = []
        for time in time_info:
            valid_time = time['validtime']
            if valid_time not in valid_time_list:
                valid_time_list.append(valid_time)
        for name in model_list:
            index = model_list.index(name)
            dir = model_dir_list[index]
            if 'gfs' in anl_name or len(anl_file_format_list) == 1:
                anl_file_format = anl_file_format_list[0]
            else:
                anl_file_format = anl_file_format_list[index]
            if 'gfs' in anl_file_format:
                anl_dump = 'gfs'
            elif 'gdas' in anl_file_format:
                anl_dump = 'gdas'
            hpss_dir = model_hpssdir_list[index]
            link_model_data_dir = os.path.join(cwd, 'data', name)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
                os.makedirs(
                    os.path.join(link_model_data_dir, 'HPSS_jobs')
                )
            for valid_time in valid_time_list:
                link_anl_file = os.path.join(
                    link_model_data_dir,
                    'anl.'+valid_time.strftime('%Y%m%d%H')
                )
                if not os.path.exists(link_anl_file):
                    anl_filename = format_filler(anl_file_format,
                                                 valid_time,
                                                 init_time, lead)
                    if anl_name == 'self_anl' or anl_name == 'self_f00':
                        anl_dir = os.path.join(dir, name)
                    elif anl_name == 'gfs_anl' or anl_name == 'gfs_f00':
                        anl_dir = os.path.join(os.environ['gstat'], 'gfs')
                    else:
                        print("ERROR: "+anl_name+" is not a valid option "
                              +"for maps2d_anl_name")
                        exit(1)
                    anl_file = os.path.join(anl_dir, anl_filename)
                    if os.path.exists(anl_file):
                        if any(
                            g in anl_file for g in grib2_file_names
                        ):
                            convert_grib2_grib1(anl_file,
                                                link_anl_file)
                        else:
                            os.system('ln -sf '+anl_file+' '+link_anl_file)
                    else:
                        if model_data_run_hpss == 'YES':
                            print("Did not find "+anl_file+" "
                                  +"online...going to try to get file from HPSS")
                            if 'self' in anl_name:
                                hpss_dir = hpss_dir
                            elif 'gfs' in anl_name:
                                hpss_dir = '/NCEPPROD/hpssprod/runhistory'
                            hpss_tar, hpss_file, hpss_job_filename = (
                                    set_up_gfs_hpss_info(valid_time, hpss_dir,
                                                         anl_dump, 'anl',
                                                         link_model_data_dir)
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_model_data_dir, link_anl_file,
                                          hpss_tar, hpss_file)
                    if not os.path.exists(link_anl_file):
                        if model_data_run_hpss == 'YES':
                            error_msg = ('WARNING: '+anl_file+' does not exist '
                                         +'and did not find HPSS file '
                                         +hpss_file+' from '+hpss_tar+' or '
                                         +'walltime exceeded')
                        else:
                            error_msg = 'WARNING: '+anl_file+' does not exist'
                        print(error_msg)
                        error_dir = os.path.join(link_model_data_dir)
                        error_file = os.path.join(
                            error_dir,
                            'error_anl_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                        )
                        if not os.path.exists(error_file):
                            with open(error_file, 'a') as file:
                                file.write(error_msg)
    # Get analysis files 
    # for if analysis in forecast_to_plot_list
    if 'anl' in forecast_to_plot_list:
        time_info = get_time_info(start_date, end_date,
                                  start_hr, end_hr, hr_inc,
                                  ['00'], make_met_data_by)
        for name in model_list:
            index = model_list.index(name)
            dir = model_dir_list[index]
            if 'gfs' in anl_name or len(anl_file_format_list) == 1:
                anl_file_format = anl_file_format_list[0]
            else:
                anl_file_format = anl_file_format_list[index]
            if 'gfs' in anl_file_format:
                anl_dump = 'gfs'
            elif 'gdas' in anl_file_format:
                anl_dump = 'gdas'
            hpss_dir = model_hpssdir_list[index]
            link_model_data_dir = os.path.join(cwd, 'data', name)
            if not os.path.exists(link_model_data_dir):
                os.makedirs(link_model_data_dir)
                os.makedirs(
                    os.path.join(link_model_data_dir, 'HPSS_jobs')
                )
            for time in time_info:
                valid_time = time['validtime']
                link_anl_file = os.path.join(
                    link_model_data_dir,
                    'anl.'+valid_time.strftime('%Y%m%d%H')                )
                if not os.path.exists(link_anl_file):
                    anl_filename = format_filler(anl_file_format,
                                                 valid_time,
                                                 init_time, lead)
                    if anl_name == 'self_anl' or anl_name == 'self_f00':
                        anl_dir = os.path.join(dir, name)
                    elif anl_name == 'gfs_anl' or anl_name == 'gfs_f00':
                        anl_dir = os.path.join(os.environ['gstat'], 'gfs')
                    else:
                        print("ERROR: "+anl_name+" is not a valid option "
                              +"for maps2d_anl_name")
                        exit(1)
                    anl_file = os.path.join(anl_dir, anl_filename)
                    if os.path.exists(anl_file):
                        if any(
                            g in anl_file for g in grib2_file_names
                        ):
                            convert_grib2_grib1(anl_file,
                                                link_anl_file)
                        else:
                            os.system('ln -sf '+anl_file+' '+link_anl_file)
                    else:
                        if model_data_run_hpss == 'YES':
                            print("Did not find "+anl_file+" "
                                  +"online...going to try to get file from HPSS")
                            if 'self' in anl_name:
                                hpss_dir = hpss_dir
                            elif 'gfs' in anl_name:
                                hpss_dir = '/NCEPPROD/hpssprod/runhistory'
                            hpss_tar, hpss_file, hpss_job_filename = (
                                    set_up_gfs_hpss_info(valid_time, hpss_dir,
                                                         anl_dump, 'anl',
                                                         link_model_data_dir)
                            )
                            get_hpss_data(hpss_job_filename,
                                          link_model_data_dir, link_anl_file,
                                          hpss_tar, hpss_file)
                    if not os.path.exists(link_anl_file):
                        if model_data_run_hpss == 'YES':
                            error_msg = ('WARNING: '+anl_file+' does not exist '
                                         +'and did not find HPSS file '
                                         +hpss_file+' from '+hpss_tar+' or '
                                         +'walltime exceeded')
                        else:
                            error_msg = 'WARNING: '+anl_file+' does not exist'
                        print(error_msg)
                        error_dir = os.path.join(link_model_data_dir)
                        error_file = os.path.join(
                            error_dir,
                            'error_anl_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                        )
                        if not os.path.exists(error_file):
                            with open(error_file, 'a') as file:
                                file.write(error_msg)
    # Get observation files
    # for model2obs
    if 'model2obs' in type_list:
        obdata_dir = os.environ['obdata_dir']
        use_ceres = os.environ['maps2d_model2obs_use_ceres']
        use_monthly_mean = os.environ['maps2d_model2obs_use_monthly_mean']
        obtype_list = ['gpcp', 'ghcn_cams']
        if use_ceres == 'YES':
            obtype_list.append('ceres')
        else:
            obtype_list.extend(['clwp', 'nvap', 'rad_isccp', 'rad_srb2'])
        print("Getting observation files...")
        link_obs_data_dir = os.path.join(cwd, 'data', 'obs')
        if not os.path.exists(link_obs_data_dir):
            os.makedirs(link_obs_data_dir)
        for obtype in obtype_list:
            os.makedirs(os.path.join(link_obs_data_dir, obtype))
            if obtype in ['clwp', 'nvap', 'rad_isccp', 'rad_srb2']:
                if use_monthly_mean == 'YES':
                    obtype_use_monthly_mean = 'NO'
                    print("Using old VSDB datasets "
                          +obtype+", must use monthly climatology")
                else:
                    obtype_use_monthly_mean = use_monthly_mean
                obtype_data_path = 'vsdb_climo_data/CF_compliant'
            else:
                obtype_use_monthly_mean = use_monthly_mean
                if use_monthly_mean == 'YES':
                    obtype_data_path = obtype+'/monthly_mean'
                else:
                    obtype_data_path = obtype+'/monthly_climo'
            for forecast_to_plot in forecast_to_plot_list:
                if forecast_to_plot == 'anl':
                    ftp_fhr_list = ['00']
                else:
                    ftp_fhr_list = []
                    if forecast_to_plot[0] == 'f':
                        ftp_fhr_list.append(forecast_to_plot[1:])
                    elif forecast_to_plot[0] == 'd':
                        fhr4 = int(forecast_to_plot[1:]) * 24
                        fhr3 = str(fhr4 - 6).zfill(2)
                        fhr2 = str(fhr4 - 12).zfill(2)
                        fhr1 = str(fhr4 - 18).zfill(2)
                        ftp_fhr_list.extend([fhr1, fhr2,
                                             fhr3, str(fhr4).zfill(2)])
                for ftp_fhr in ftp_fhr_list:
                    time_info = get_time_info(start_date, end_date,
                                              start_hr, end_hr, hr_inc,
                                              [ftp_fhr], make_met_data_by)
                    for time in time_info:
                        valid_time = time['validtime']
                        if obtype_use_monthly_mean == 'YES':
                            obtype_filename = (
                                obtype+'_'+valid_time.strftime('%B')[0:3]
                                +valid_time.strftime('%Y')+'.nc'
                            )
                        else:
                            obtype_filename = (
                                obtype+'_'+valid_time.strftime('%B')[0:3]
                                +'.nc'
                            )
                        obtype_file = os.path.join(obdata_dir,
                                                   obtype_data_path,
                                                   obtype_filename)
                        link_obtype_file = os.path.join(link_obs_data_dir,
                                                        obtype,
                                                        obtype_filename)
                        if not os.path.exists(link_obtype_file):
                            if not os.path.exists(obtype_file):
                                if obtype_use_monthly_mean == 'YES':
                                    print("WARNING: "+obtype_file+" "
                                          +"does not exist...linking "
                                          +"climatology file instead")
                                    obtype_file = obtype_file \
                                        .replace('monthly_mean',
                                                 'monthly_climo') \
                                        .replace(valid_time.strftime('%Y'),
                                                 '')
                            if os.path.exists(obtype_file):
                                os.system('ln -sf '+obtype_file
                                          +' '+link_obtype_file)
    # Create file lists for MET's series_analysis
    for forecast_to_plot in forecast_to_plot_list:
        if 'model2obs' in type_list:
            print("Creating model and observation file lists for MET's "
                  +"series_analysis for "+forecast_to_plot)
        else:
            print("Creating model file lists for MET's "
                  +"series_analysis for "+forecast_to_plot)
        if forecast_to_plot == 'anl':
            ftp_fhr_list = ['00']
        else:
            ftp_fhr_list = []
            if forecast_to_plot[0] == 'f':
                ftp_fhr_list.append(forecast_to_plot[1:])
            elif forecast_to_plot[0] == 'd':
                fhr4 = int(forecast_to_plot[1:]) * 24
                fhr3 = str(fhr4 - 6).zfill(2)
                fhr2 = str(fhr4 - 12).zfill(2)
                fhr1 = str(fhr4 - 18).zfill(2)
                ftp_fhr_list.extend([fhr1, fhr2, fhr3, str(fhr4).zfill(2)])
        for ftp_fhr in ftp_fhr_list:
            time_info = get_time_info(start_date, end_date,
                                      start_hr, end_hr, hr_inc,
                                      [ftp_fhr], make_met_data_by)
            for time in time_info:
                valid_time = time['validtime']
                init_time = time['inittime']
                lead = time['lead']
                if init_time.strftime('%H') in ['03', '09', '15', '21']:
                    continue
                else:
                    analysis_filename= (
                        'anl.'+valid_time.strftime('%Y%m%d%H')
                    )
                    forecast_filename = (
                        'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                    )
                    # Check all files needed for all models exist
                    all_files_exist = True
                    for name in model_list:
                        model_data_dir = os.path.join(cwd, 'data', name)
                        model_analysis_file = os.path.join(
                            model_data_dir,
                            analysis_filename
                        )
                        model_forecast_file = os.path.join(
                            model_data_dir,
                            forecast_filename
                        )
                        if forecast_to_plot == 'anl':
                            if not os.path.exists(model_analysis_file):
                                all_files_exist = False
                        else:
                            if not os.path.exists(model_forecast_file):
                                all_files_exist = False
                            if forecast_anl_diff == 'YES':
                                if not os.path.exists(model_analysis_file):
                                    all_files_exist = False
                    # If all files exist, write to file
                    if all_files_exist:
                        for name in model_list:
                            model_data_dir = os.path.join(cwd, 'data', name)
                            model_analysis_file = os.path.join(
                                model_data_dir,
                                analysis_filename
                            )
                            model_forecast_file = os.path.join(
                                model_data_dir,
                                forecast_filename
                            )
                            forecast_to_plot_file_list_filename = os.path.join(
                                model_data_dir,
                                name+'_'+forecast_to_plot+'_file_list.txt'
                            )
                            forecast_to_plot_file_list_file = open(
                                forecast_to_plot_file_list_filename, 'a'
                            )
                            if (forecast_anl_diff == 'YES'
                                    and forecast_to_plot != 'anl'):
                                forecast_to_plot_anl_file_list_filename = (
                                    os.path.join(model_data_dir,
                                                 name+'_'+forecast_to_plot
                                                 +'_anl_file_list.txt')
                                )
                                forecast_to_plot_anl_file_list_file = open(
                                    forecast_to_plot_anl_file_list_filename,
                                    'a'
                                )
                            if forecast_to_plot == 'anl':
                                forecast_to_plot_file_list_file.write(
                                    model_analysis_file+'\n'
                                )
                            else:
                                forecast_to_plot_file_list_file.write(
                                    model_forecast_file+'\n'
                                )
                                if forecast_anl_diff == 'YES':
                                    forecast_to_plot_anl_file_list_file.write(
                                        model_analysis_file+'\n'
                                    )
                                    forecast_to_plot_anl_file_list_file.close()
                            forecast_to_plot_file_list_file.close()
                        # Check and write files for observations
                        for obtype in obtype_list:
                            link_obs_data_dir = os.path.join(cwd,
                                                             'data',
                                                             'obs')
                            if obtype in ['clwp', 'nvap', 'rad_isccp', 
                                          'rad_srb2']:
                                if use_monthly_mean == 'YES':
                                    obtype_use_monthly_mean = 'NO'
                                else:
                                    obtype_use_monthly_mean = use_monthly_mean
                            else:
                                obtype_use_monthly_mean = use_monthly_mean
                            if obtype_use_monthly_mean == 'YES':
                                obtype_file = os.path.join(
                                    link_obs_data_dir, obtype,
                                    obtype+'_'+valid_time.strftime('%B')[0:3]
                                    +valid_time.strftime('%Y')+'.nc'
                                )
                            else:
                                obtype_file = os.path.join(
                                    link_obs_data_dir, obtype,
                                    obtype+'_'+valid_time.strftime('%B')[0:3]
                                    +'.nc'
                                )
                            obtype_forecast_to_plot_file_list_filename = (
                                os.path.join(link_obs_data_dir, obtype,
                                             obtype+'_'+forecast_to_plot
                                             +'_file_list.txt')
                            )
                            obtype_forecast_to_plot_file_list_file = open(
                                obtype_forecast_to_plot_file_list_filename,'a'
                            )
                            obtype_forecast_to_plot_file_list_file.write(
                                obtype_file+'\n'
                            )
                            obtype_forecast_to_plot_file_list_file.close()
elif RUN == 'mapsda':
    # Read in environment variables
    type_list = os.environ['mapsda_type_list'].split(' ')
    start_hr = os.environ['mapsda_hr_beg']
    end_hr = os.environ['mapsda_hr_end']
    hr_inc = os.environ['mapsda_hr_inc']
    gdas_make_met_data_by = os.environ['mapsda_gdas_make_met_data_by']
    gdas_guess_hour = os.environ['mapsda_gdas_guess_hour']
    gdas_model_fileformat_list = (
        os.environ['mapsda_gdas_model_fileformat_list'].split(' ')
    )
    gdas_anl_fileformat_list = (
        os.environ['mapsda_gdas_anl_fileformat_list'].split(' ')
    )
    ens_make_met_data_by = os.environ['mapsda_ens_make_met_data_by']
    ens_guess_hour = os.environ['mapsda_ens_guess_hour']
    ens_model_dir_list = os.environ['mapsda_ens_model_dir_list'].split(' ')
    ens_netcdf_suffix_list = (
        os.environ['mapsda_ens_netcdf_suffix_list'].split(' ')
    )
    # Go through type list
    for type in type_list:
        if type == 'gdas':
            forecast_to_plot_list = [gdas_guess_hour]
            make_met_data_by = gdas_make_met_data_by
            model_data_run_hpss = model_data_run_hpss
        elif type == 'ens':
            forecast_to_plot_list = [ens_guess_hour]
            make_met_data_by = ens_make_met_data_by
            model_data_run_hpss = os.environ['mapsda_ens_model_data_runhpss']
        # Get date and time information
        time_info = get_time_info(start_date, end_date, start_hr, end_hr,
                                  hr_inc, forecast_to_plot_list,
                                  make_met_data_by)
        if type == 'gdas':
            model_fileformat_list = gdas_model_fileformat_list
            anl_fileformat_list = gdas_anl_fileformat_list
            # Get model forecast files
            cwd = os.getcwd()
            for name in model_list:
                index = model_list.index(name)
                dir = model_dir_list[index]
                file_format = model_fileformat_list[index]
                if 'gfs' in file_format:
                    dump = 'gfs'
                elif 'gdas' in file_format:
                    dump = 'gdas'
                hpss_dir = model_hpssdir_list[index]
                link_model_data_dir = os.path.join(cwd, 'data', name)
                if not os.path.exists(link_model_data_dir):
                    os.makedirs(link_model_data_dir)
                    os.makedirs(
                        os.path.join(link_model_data_dir, 'HPSS_jobs')
                    )
                for time in time_info:
                    valid_time = time['validtime']
                    init_time = time['inittime']
                    lead = time['lead']
                    if init_time.strftime('%H') in ['03', '09', '15', '21']:
                        continue
                    else:
                        link_model_forecast_file = os.path.join(
                            link_model_data_dir,
                            'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                        )
                        if not os.path.exists(link_model_forecast_file):
                            model_forecast_filename = format_filler(
                                file_format, valid_time, init_time, lead
                            )
                            model_forecast_file = os.path.join(
                                dir, name, model_forecast_filename
                            )
                            if os.path.exists(model_forecast_file):
                                if any(
                                    g in model_forecast_file \
                                    for g in grib2_file_names
                                ):
                                    convert_grib2_grib1(
                                        model_forecast_file,
                                        link_model_forecast_file
                                    )
                                else:
                                    os.system('ln -sf '
                                              +model_forecast_file+' '
                                              +link_model_forecast_file)
                            else:
                                if model_data_run_hpss == 'YES':
                                    print("Did not find "
                                          +model_forecast_file+" "
                                          +"online...going to try "
                                          +"to get file from HPSS")
                                    hpss_tar, hpss_file, hpss_job_filename = (
                                        set_up_gfs_hpss_info(
                                            init_time, hpss_dir, dump,
                                            'f'+lead.zfill(3),
                                            link_model_data_dir
                                        )
                                    )
                                    get_hpss_data(hpss_job_filename,
                                                  link_model_data_dir,
                                                  link_model_forecast_file,
                                                  hpss_tar, hpss_file)
                        if not os.path.exists(link_model_forecast_file):
                            if model_data_run_hpss == 'YES':
                                print("WARNING: "+model_forecast_file+" "
                                      +"does not exist and did not find "
                                      +"HPSS file "+hpss_file+" from "
                                      +hpss_tar+" or walltime exceeded")
                            else:
                                print("WARNING: "+model_forecast_file+" "
                                      +"does not exist")
            # Get model "truth" files
            valid_time_list = []
            for time in time_info:
                valid_time = time['validtime']
                if valid_time not in valid_time_list:
                    valid_time_list.append(valid_time)
            for name in model_list:
                index = model_list.index(name)
                dir = model_dir_list[index]
                if len(anl_fileformat_list) == 1:
                    anl_file_format = anl_fileformat_list[0]
                else:
                    anl_file_format = anl_fileformat_list[index]
                if 'gfs' in anl_file_format:
                    anl_dump = 'gfs'
                elif 'gdas' in anl_file_format:
                    anl_dump = 'gdas'
                hpss_dir = model_hpssdir_list[index]
                link_model_data_dir = os.path.join(cwd, 'data', name)
                if not os.path.exists(link_model_data_dir):
                    os.makedirs(link_model_data_dir)
                    os.makedirs(
                        os.path.join(link_model_data_dir, 'HPSS_jobs')
                    )
                for valid_time in valid_time_list:
                    link_anl_file = os.path.join(
                        link_model_data_dir,
                        'anl.'+valid_time.strftime('%Y%m%d%H')
                    )
                    if not os.path.exists(link_anl_file):
                        anl_filename = format_filler(anl_file_format,
                                                     valid_time,
                                                     init_time, lead)
                        anl_dir = os.path.join(dir, name)
                        anl_file = os.path.join(anl_dir, anl_filename)
                        if os.path.exists(anl_file):
                            if any(
                                g in anl_file \
                                for g in grib2_file_names
                            ):
                                convert_grib2_grib1(anl_file,
                                                    link_anl_file)
                            else:
                                os.system('ln -sf '+anl_file+' '
                                          +link_anl_file)
                        else:
                            if model_data_run_hpss == 'YES':
                                print("Did not find "+anl_file+" "
                                      +"online...going to try to get file "
                                      +"from HPSS")
                                hpss_dir = hpss_dir
                                hpss_tar, hpss_file, hpss_job_filename = (
                                    set_up_gfs_hpss_info(
                                         valid_time, hpss_dir, anl_dump,
                                         'anl', link_model_data_dir
                                    )
                                )
                                get_hpss_data(hpss_job_filename,
                                              link_model_data_dir,
                                              link_anl_file,
                                              hpss_tar, hpss_file)
                    if not os.path.exists(link_anl_file):
                        if model_data_run_hpss == 'YES':
                            error_msg = ('WARNING: '+anl_file+' does not '
                                         +'exist and did not find HPSS file '
                                         +hpss_file+' from '+hpss_tar+' or '
                                         +'walltime exceeded')
                        else:
                            error_msg = 'WARNING: '+anl_file+' does not exist'
                        print(error_msg)
                        error_dir = os.path.join(link_model_data_dir)
                        error_file = os.path.join(
                            error_dir,
                            'error_anl_'+valid_time.strftime('%Y%m%d%H%M')+'.txt'
                        )
                        if not os.path.exists(error_file):
                            with open(error_file, 'a') as file:
                                file.write(error_msg)
            # Create file lists for MET's series_analysis
            for forecast_to_plot in forecast_to_plot_list:
                print("Creating model file lists for MET's "
                      +"series_analysis for "+forecast_to_plot+" and "
                      +"analysis")
                time_info = get_time_info(start_date, end_date,
                                          start_hr, end_hr, hr_inc,
                                          [forecast_to_plot],
                                          make_met_data_by)
                for time in time_info:
                    valid_time = time['validtime']
                    init_time = time['inittime']
                    lead = time['lead']
                    if init_time.strftime('%H') in ['03', '09', '15', '21']:
                        continue
                    else:
                        analysis_filename= (
                            'anl.'+valid_time.strftime('%Y%m%d%H')
                        )
                        forecast_filename = (
                            'f'+lead+'.'+init_time.strftime('%Y%m%d%H')
                        )
                        # Check all files needed for all models exist
                        all_files_exist = True
                        for name in model_list:
                            model_data_dir = os.path.join(cwd, 'data', name)
                            model_analysis_file = os.path.join(
                                model_data_dir,
                                analysis_filename
                            )
                            model_forecast_file = os.path.join(
                                model_data_dir,
                                forecast_filename
                            )
                            if not os.path.exists(model_forecast_file):
                                all_files_exist = False
                            if not os.path.exists(model_analysis_file):
                                all_files_exist = False
                        # If all files exist, write to file
                        if all_files_exist:
                            for name in model_list:
                                model_data_dir = os.path.join(cwd, 'data',
                                                              name)
                                model_analysis_file = os.path.join(
                                    model_data_dir,
                                    analysis_filename
                                )
                                model_forecast_file = os.path.join(
                                    model_data_dir,
                                    forecast_filename
                                )
                                forecast_to_plot_file_list_filename = (
                                    os.path.join(model_data_dir,
                                                 name+'_'+
                                                 forecast_to_plot
                                                 +'_file_list.txt')
                                )
                                forecast_to_plot_file_list_file = open(
                                    forecast_to_plot_file_list_filename, 'a'
                                )
                                forecast_to_plot_anl_file_list_filename = (
                                    os.path.join(model_data_dir,
                                                 name+'_'+forecast_to_plot
                                                 +'_anl_file_list.txt')
                                )
                                forecast_to_plot_anl_file_list_file = open(
                                    forecast_to_plot_anl_file_list_filename,
                                    'a'
                                )
                                forecast_to_plot_file_list_file.write(
                                    model_forecast_file+'\n'
                                )
                                forecast_to_plot_anl_file_list_file.write(
                                    model_analysis_file+'\n'
                                )
                                forecast_to_plot_anl_file_list_file.close()
                                forecast_to_plot_file_list_file.close()
        elif type == 'ens':
            # Get model forecast files
            cwd = os.getcwd()
            for name in model_list:
                index = model_list.index(name)
                dir = ens_model_dir_list[index]
                netcdf_suffix = ens_netcdf_suffix_list[index]
                hpss_dir = model_hpssdir_list[index]
                link_model_data_dir = os.path.join(cwd, 'data', name)
                if not os.path.exists(link_model_data_dir):
                    os.makedirs(link_model_data_dir)
                    os.makedirs(
                        os.path.join(link_model_data_dir, 'HPSS_jobs')
                    )
                dump = 'gdas'
                for file_type in ['mean', 'spread']:
                    if ens_guess_hour == 'anl':
                        file_format = (
                            'enkf'+dump+'.{init?fmt=%Y%m%d}/{cycle?fmt=%H}/'
                            +dump+'.t{cycle?fmt=%H}z.atmanl.ens'
                            +file_type+'.'+netcdf_suffix
                        )
                    else:
                        file_format = (
                            'enkf'+dump+'.{init?fmt=%Y%m%d}/{cycle?fmt=%H}/'
                            +dump+'.t{cycle?fmt=%H}z.atmf0{lead?fmt=%H}.ens'
                            +file_type+'.'+netcdf_suffix
                        )
                    exisiting_file_list = ''
                    for time in time_info:
                        valid_time = time['validtime']
                        init_time = time['inittime']
                        lead = time['lead']
                        if init_time.strftime('%H') in ['03', '09', 
                                                        '15', '21']:
                            continue
                        else:
                            if ens_guess_hour == 'anl':
                                link_model_forecast_file = os.path.join(
                                    link_model_data_dir,
                                    'atmanl.ens'+file_type+'.'
                                    +init_time.strftime('%Y%m%d%H')+'.'
                                    +netcdf_suffix
                                )
                            else:
                                link_model_forecast_file = os.path.join(
                                    link_model_data_dir,
                                    'atmf0'+lead+'.ens'+file_type+'.'
                                    +init_time.strftime('%Y%m%d%H')+'.'
                                    +netcdf_suffix
                                )
                            if not os.path.exists(link_model_forecast_file):
                                model_forecast_filename = format_filler(
                                    file_format, valid_time, init_time, lead
                                )
                                model_forecast_file = os.path.join(
                                    dir, model_forecast_filename
                                )
                                if os.path.exists(model_forecast_file):
                                    os.system('ln -sf '
                                              +model_forecast_file+' '
                                              +link_model_forecast_file)
                                else:
                                    if model_data_run_hpss == 'YES':
                                        print("Did not find "
                                              +model_forecast_file+" "
                                              +"online...going to try  "
                                              +"to get file from HPSS")
                                        if ens_guess_hour == 'anl':
                                            lead_time = 'anl'
                                        else:
                                            lead_time = 'f0'+lead
                                        (hpss_tar, hpss_file,
                                             hpss_job_filename) = (
                                            set_up_gfs_hpss_info(
                                                init_time, hpss_dir,
                                                'enkf'+dump,
                                                'atm'+lead_time+'.ens'
                                                +file_type+'.'+netcdf_suffix,
                                                link_model_data_dir
                                            )
                                        )
                                        get_hpss_data(hpss_job_filename,
                                                      link_model_data_dir,
                                                      link_model_forecast_file,
                                                      hpss_tar, hpss_file)
                            if not os.path.exists(link_model_forecast_file):
                                if model_data_run_hpss == 'YES':
                                    print("WARNING: "+model_forecast_file+" "
                                          +"does not exist and did not find "
                                          +"HPSS file "+hpss_file+" from "
                                          +hpss_tar+" or walltime exceeded")
                                else:
                                    print("WARNING: "+model_forecast_file+" "
                                          +"does not exist")
                            else:
                                exisiting_file_list = (
                                  exisiting_file_list
                                  +link_model_forecast_file+' '
                                )
                    if ens_guess_hour == 'anl':
                        avg_file = os.path.join(
                            cwd, 'data', name,
                            'atmanl.ens'+file_type+'.nc' 
                        )
                    else:
                        avg_file = os.path.join(
                            cwd, 'data', name,
                            'atmf0'+lead+'.ens'+file_type+'.nc'
                        )
                    print("Creating average files for "+name+" "
                          +"ens"+file_type+" from available data. "
                          +"Saving as "+avg_file)
                    ncea_cmd = subprocess.check_output(
                        'which ncea', shell=True
                    ).replace('\n', '')
                    if netcdf_suffix == 'nc4':
                        process_vars = ''
                    elif netcdf_suffix == 'nc':
                        process_vars = (
                            ' -v tmp,ugrd,vgrd,spfh,pressfc,o3mr,clwmr '
                        )
                    os.system(ncea_cmd+' '+exisiting_file_list
                              +' -o '+avg_file+process_vars)

print("END: "+os.path.basename(__file__))
