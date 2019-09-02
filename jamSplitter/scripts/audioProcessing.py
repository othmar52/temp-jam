# -*- coding: utf-8 -*-

# TODO rename to mediaProcessing.py as video thumb extraction is also within this file

import json
import logging
import time
import subprocess
import os
import re
from shutil import copyfile

# this snippet is already in jamSplitter.py
# TODO remove
try:
    from termcolor import colored
except ImportError:
    def colored(str, col=''):
        return str

def generalCmd(cmdArgsList, description, readStdError = False):
    logging.info("starting %s" % description)    
    logging.debug(' '.join(cmdArgsList))
    startTime = time.time()
    if readStdError:
        process = subprocess.Popen(cmdArgsList, stderr=subprocess.PIPE)
        processStdOut = process.stderr.read()
    else:
        process = subprocess.Popen(cmdArgsList, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        processStdOut = process.stdout.read()
    retcode = process.wait()
    if retcode != 0:
        print ( "ERROR: %s did not complete successfully (error code is %s)" % (description, retcode) )

    logging.info("finished %s in %s seconds" % ( description, '{0:.3g}'.format(time.time() - startTime) ) )
    return processStdOut.decode('utf-8')

def convertWavToMp3(inputPath, outputPath, bitrate, track):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-v', 'quiet', '-stats',
        '-i', str(inputPath),
        '-metadata', ('artist=%s' % track.artist),
        '-metadata', ('author=%s' % track.artist),
        '-metadata', ('album_artist=%s' % track.artist),
        '-metadata', ('album=%s' % track.album),
        '-metadata', ('title=%s' % track.trackTitle),
        #'-metadata', ('date=%s' % track.artist),
        #'-metadata', ('year=%s' % track.artist),
        '-metadata', ('genre=%s' % track.genre),
        '-metadata', ('track=%s' % track.trackNumber),
        '-c:a', 'libmp3lame',
        '-ab', ('%sk'%bitrate),
        str(outputPath)
    ]
    generalCmd(cmd, 'wav to mp3 conversion')

def captureVideoFrame(inputPath, outputPath, second=5):
    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPath), '-vcodec', 'png', '-ss', str(second),
        '-vframes', '1', '-an', '-f', 'rawvideo',
        str(outputPath)
    ]
    generalCmd(cmd, 'capture video frame')

def resampleWav(inputPath, outputPath):
    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPath), '-c:a', 'pcm_s16le', '-ar', '4096',
        str(outputPath)
    ]
    generalCmd(cmd, 'resample wav')

def extractWavPeaks(scriptPath, inputPath, amount=2000):
    lowBitrateWavPath = ('%s.low.wav' % str(inputPath))
    resampleWav(inputPath, lowBitrateWavPath)
    cmd = [
        'php',
        str(scriptPath),
        ('-i%s' % str(lowBitrateWavPath) ),
        ('-n%s' % str(amount) )
    ]
    processStdOut = generalCmd(cmd, 'extract wav peaks')
    return processStdOut.strip().split(',')

def detectBpm(inputPath, method):
    # available methods are soundstretch|bpmdetect
    # /usr/bin/soundstretch WAVFILE /dev/null -bpm=n 2>&1 | grep "Detected BPM rate" | awk '{ print $4 }' | xargs
    # /usr/bin/bpmdetect -c -p -d WAVFILE | sed -e 's:BPM::g' | xargs
    
    if method == 'soundstretch':
        cmd = [
            'soundstretch',
            str(inputPath),
            '/dev/null',
            '-bpm=n'
        ]
        processStdOut = generalCmd(cmd, 'bpm detection')

        pattern = "^(.*)Detected\ BPM\ rate\ ([0-9.]{1,5})(.*)$"
        searchIn = ' '.join(processStdOut.split())
        match = re.match( pattern, searchIn )
        if match:
            logging.info("BPM SUCCESS '%s'" % match.group(2))
            return str(bpmBoundries(float(match.group(2))))

        logging.warning(" no result of BPM detection")
        return 0
    
    if method == 'bpmdetect':
        print (colored ( "TODO: BPM detect method 'bpmdetect' not implemented yet. use soundstretch", "red"))
        return 0
    logging.warning("invalid method for bpm detect..." )
    return 0

def bpmBoundries(inputBpm):
    lowerBoundry = 70
    upperBoundry = 180
    if inputBpm < 0.1:
        return 0
    if inputBpm > lowerBoundry and inputBpm < upperBoundry:
        return inputBpm
    if inputBpm < lowerBoundry:
        # avoid endless recursion caused by too small range
        if (inputBpm*2) > upperBoundry:
            return inputBpm
        return bpmBoundries(inputBpm*2)
    if inputBpm > upperBoundry:
        # avoid endless recursion caused by too small range
        if (inputBpm/2) < lowerBoundry:
            return inputBpm
        return bpmBoundries(inputBpm/2)

def isSilenceFile(inputPath, inputFileDuration):
    # TODO move dbLevel to config
    dbLevel = '-40dB'
    silenceDuration = inputFileDuration - 0.1
    cmd = [
        'ffmpeg', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', ('silencedetect=noise=%s:d=%s' % (dbLevel, silenceDuration) ),
        '-f','null', '-'
    ]
    processStdOut = generalCmd(cmd, 'silence detection')
    if 'silence_start:' in processStdOut.split():
        return True
    return False

def detectSilences(inputPath, dbLevel = '-45dB', silenceDuration = 2):
    # TODO move args to config
    cmd = [
        'ffmpeg', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', ('silencedetect=noise=%s:d=%i' % (dbLevel, silenceDuration) ),
        '-f','null', '-'
    ]
    return generalCmd(cmd, 'silence detection', True)


def muteNoiseSections(inputPath, outputPath, silences):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-stats', '-i', str(inputPath),
        '-af', f', '.join(silences),
        str(outputPath)
    ]
    return generalCmd(cmd, 'muting noise sections', True)

def mergeInputWavsToSingleFile(inputPaths, outputPath):

    cmd = ['ffmpeg', '-y', '-hide_banner', '-v', 'quiet', '-stats']
    for inputFile in inputPaths:
        cmd += [ '-i', str(inputFile)]

    # TODO why does amix decrease all volume levels? is "volume=2" or "volume=[N tracks]" correct???
    cmd += ['-filter_complex', ('amix=inputs=%d:duration=longest:dropout_transition=3,volume=2' % len(inputPaths) )]
    cmd += [str(outputPath)]
    
    generalCmd(cmd, 'merge wavs')


def createWavSplit(inputPath, outputPath, secondStart, secondEnd):
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-v', 'quiet', '-stats',
        '-i', inputPath, '-ss', str(secondStart), '-to', str(secondEnd),
        '-c:a', 'pcm_s16le', '-ar', '44100', outputPath
    ]
    generalCmd(cmd, 'split wav')


def appendSilenceToWav(inputPath, outputPath, seconds):

    silenceFilePath = ("%s.silence-%s.wav" % (str(outputPath), seconds ) )
    cmdCreateSilence = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-f', 'lavfi', '-y',
        '-i', 'anullsrc', '-t', seconds, '-c:a', 'pcm_s16le', '-ar', '44100',
        silenceFilePath
    ]
    generalCmd(cmdCreateSilence, 'create silence')

    cmdConcat = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', inputPath, '-i', silenceFilePath, '-filter_complex',
        '[0:0][1:0]concat=n=2:v=0:a=1[out]', '-map', '[out]', outputPath
    ]
    generalCmd(cmdConcat, 'concat wavs')
    
    
def detectDuration(filePath):
    cmd = [
        'ffprobe', '-i', str(filePath),
        '-show_entries', 'format=duration',
        '-v', 'quiet', '-of', 'csv=p=0'
    ]
    processStdOut = generalCmd(cmd, 'detect duration')
    return float(processStdOut.strip())


def detectVolume(filePath):
    cmd = [
        'ffmpeg', '-hide_banner', '-i', filePath,
        '-af', 'volumedetect', '-f', 'null', '/dev/null'
    ]
    processStdOut = generalCmd(cmd, 'volume detection', True)
    
    volJSON = json.loads('{}')
    pattern = ".*Parsed_volumedetect.*\]\ (.*)\:\ ([0-9.-]*)"
    for line in processStdOut.split('\n'):
        match = re.match( pattern, line)
        if match:
            volJSON[match.group(1)] = match.group(2)
    
    return volJSON


def normalizeWav(inputFilePath, outputFilePath):
    samplerate = '44100'
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-i', inputFilePath, '-af',
        #'dynaudnorm=f=150:p=0.71:m=100:s=12:g=15',
        'dynaudnorm=m=100',
        #'-c:a', 'pcm_s16le', '-ar', samplerate, 
        outputFilePath
    ]
    generalCmd(cmd, 'normalize wav (dynaudionorm)')


# @see https://gist.github.com/kylophone/84ba07f6205895e65c9634a956bf6d54
# @see http://k.ylo.ph/2016/04/04/loudnorm.html
# unfortunately this is very slow with unsatifying results (not used at the moment)    
def normalizeWavDoublePass(inputFilePath, outputFilePath):
    targetIL  = '-24.0'
    targetLRA = '+11.0'
    targetTP  = '-0.0'
    samplerate = '44100'
    cmdFirstPass = [
        'ffmpeg', '-hide_banner', '-i', inputFilePath, '-af',
        ( 'loudnorm=I=%s:LRA=%s:tp=%s:print_format=json' % (targetIL, targetLRA, targetTP) ),
        '-f', 'null', '-'
    ]
    processStdErr = generalCmd(cmdFirstPass, '1st normalization pass', True)

    stats = json.loads('\n'.join(processStdErr.splitlines()[-12:]))
    
    if stats['output_i'] < stats['input_i']:
        copyfile(inputFilePath, outputFilePath)
        stats['skipped'] = 1
        return stats

    cmdSecondPass = [
        'ffmpeg', '-y', '-hide_banner', '-i', inputFilePath,
        '-af',
        (
            'loudnorm=print_format=summary:linear=true:%s:LRA=%s:tp=%s:measured_I=%s:measured_LRA=%s:measured_tp=%s:measured_thresh=%s:offset=%s'
            % ( targetIL, targetLRA,targetTP, stats['input_i'],stats['input_lra'],stats['input_tp'],stats['input_thresh'],stats['target_offset'] )
        ),
        '-c:a', 'pcm_s16le', '-ar', samplerate, outputFilePath
    ]
    generalCmd(cmdSecondPass, '2nd normalization pass', True)
    return stats
