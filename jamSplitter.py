#!/bin/env python3
# -*- coding: utf-8 -*-

# TODO properly normalizing https://gist.github.com/kylophone/84ba07f6205895e65c9634a956bf6d54
#           session # 8 has heavy distortion passages
# TODO removal of output directory after processing in case it is empty
# TODO never convert mono stems to stereo target files?
# TODO cursor is missing in shell after executing script
#   first appearance was after implementing concurrent futures
#   typing "reset" brings back the cursor again
# TODO use dom parser to inject javascript paths
# TODO choose between trackLetter OR trackNumber by configuration
# TODO normalize + volumeDetect BEFORE concatenating silence?
# TODO check split silence before splitting ?
# TODO auto increment counter of last session
# TODO handle split detection with html player visualization
# TODO replace wavPeak detection (currently php script) with python
# TODO remove webstem session dir in case it exists ()
# TODO multiple musician names within single input filename like "john-donald.wav"
# TODO test the whole thing on windows
#   TODO replace symlink stuff of webstemplayer with hard copies on windows
# separate repository for trackname generator?

# TODO improve silence detection: @see session 17 B astl which only has a tiny pop at the beginning

# TODO WARNING: all stems seems to be silence. skipping track...
## 7 B fehlt
#                   processing track 8/9: H - Bad Bronzer [22:43]
#                        ERROR:concurrent.futures:exception calling callback for <Future at 0x7f04280bbef0 state=finished returned NoneType>
#                                          AttributeError: 'NoneType' object has no attribute 'trackLetter'

# TODO implement parallelisation within a single track processing
#     processing track 14/14: N - Swarovski Gazebo [08:20] is not parallel at all
# TODO disable dupes in suffix & prefix of random track name
# progress bar in stdout
# http://danshiebler.com/2016-09-14-parallel-progress-bar/

# time /MUSIC/_swapfile/stromwerk/00NEW/jamSplitter.py -i /run/media/engine/Stromwerk/raw/0019.1-2017.07.16-coach/raw/
# time /MUSIC/_swapfile/stromwerk/00NEW/jamSplitter.py -i /MUSIC/_swapfile/stromwerk/INc-TEMP/RAW-10-min/
# time for i in $( find /run/media/engine/Stromwerk/ -mindepth 2 -name raw -type d | sort ); do /MUSIC/_swapfile/stromwerk/00NEW/jamSplitter.py -i "$i"; done

# benchmark 9.12.2018 (8 workers)
#  57 sessions
#  real    632m18,401s  = 10,5 hours
#  user    1006m44,385s = 16,7 hours
#  sys     62m7,803s
#  = ~ 10,5 hours
#  = ~ 11 min/session

# benchmark 24.12.2018 (5 workers)
#  59 sessions
#  real    618m44,696s = 10,3 hours
#  user    1068m2,257s = 17,8 hours
#  sys     75m28,561s

#  = ~ 10,3 hours
#  = ~ 10,4 min/session

# benchmark 21.01.2019 ( 5 workers )
#  63 sessions
#  real    628m58,125s = 10,4 hours
#  user    1027m50,861s = 17 hours
#  sys     54m25,763s
#
#  = ~ 10,4 hours
#  = ~ 10 min/session

import argparse
import configparser
import fnmatch
import datetime
import locale
import json
import os
import re
import logging
# requires "Pillow" package
from PIL import Image, ImageOps
import hashlib
import random
import secrets
from shutil import copyfile, copytree, rmtree
import sys
import subprocess
import time
import concurrent.futures
from pathlib import Path

from jamSplitter import *

try:
    from termcolor import colored
except ImportError:
    def colored(str, col=''):
        return str

# TODO move functions to external files. without having global variable issues...
#currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
#parentdir = ("%s/jamSplitter/scripts" % currentdir)
#sys.path.insert(0,parentdir) 
#from helperFunctions import *

# TODO colorized cli output. but only if module is available

class _Getch:
    """Gets a single character from standard input.  Does not echo to the screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()


class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()
    
    

class JamSession(object):
    def __init__(self):
        self.counter = None
        self.paddedCounter = None
        self.dateString = None
        self.day = '??'
        self.month = '???'
        self.year = '????'
        self.dirName = ''
        self.uniqueSortedShorties = []
        self.inputFiles = []
        self.tracks = []
        self.duration = 0

class InputFile(object):
    def __init__(self, pathObj):
        self.path = pathObj
        self.uniqueStemName = ''
        self.originalName = ''
        self.musicianShorty = None
        self.duration = 0
        # use same (random) color for all tracks in session
        self.color = ''
        
class Stem(object):
    def __init__(self, pathObj):
        self.path = pathObj
        self.uniqueStemName = ''
        self.originalName = ''
        self.musicianShorty = None
        self.duration = 0
        self.byteSize = 0
        self.color = ''
        self.sorting = 0
        self.volume = 1
        self.normLevels = {
            'vanilla': {},      # volume levels of original file
            'normalized': {}    # volume levels of normalized file
        }
        self.wavPeaks = []

class Track(object):
    def __init__(self):
        self.dirName = ''
        self.startSecond = None
        self.endSecond = None
        self.duration = 0
        self.trackTitle = ''
        self.trackNumber = None
        self.byteSize = 0
        self.trackNumberPaddedZero = None
        self.bpm = 0
        # TODO add more properties for tags...
        self.artist = ''
        self.album = ''
        self.genre = ''
        # @see https://ffmpeg.org/ffmpeg-filters.html#loudnorm
        # hopefully we can set initial volume levels for normalized stems based on one of those values
        self.dbLevelsInputFiles = {
            'meanVolumeMin': 0,
            'meanVolumeMax': -1000,
            'maxVolumeMin': 0,
            'maxVolumeMax': -1000
        }
        self.webStemConfigJsFile = None
        self.tracklistJsFile = None
        self.stems = []

class WebStemPlayer(object):
    def __init__(self, templateDir):
        self.templateDir = templateDir
        self.htmlTemplate = Path('%s/index.htm' % str(self.templateDir))
        self.playerDir = Path('%s/data/stemplayer' % str(self.templateDir))
        self.trackConfigTemplate = Path('%s/trackConfigTemplate.js' % str(self.templateDir))
        self.stemConfigTemplate = Path('%s/stemConfigTemplate.js' % str(self.templateDir))
        self.imageConfigTemplate = Path('%s/imageConfigTemplate.js' % str(self.templateDir))
        self.videoConfigTemplate = Path('%s/videoConfigTemplate.js' % str(self.templateDir))
        self.tracklistConfigTemplate = Path('%s/tracklistConfigTemplate.js' % str(self.templateDir))
        self.targetDir = None
        self.baseHtmlName = ''
        self.baseHtml = None
        self.tracklistJsFile = None

class ImageFile(object):
    def __init__(self, pathObj):
        self.path = pathObj
        self.newFileName = ''
        self.dateTime = None
        self.byteSize = 0
        self.thumbTargetPath = ''

class VideoFile(object):
    def __init__(self, pathObj):
        self.path = pathObj
        self.newFileName = ''
        self.dateTime = None
        self.byteSize = 0
        self.thumbTargetPath = ''
        self.stillTargetPath = ''
        
class JamConf(object):
    def __init__(self):
        self.thisScriptPath = Path(os.path.dirname(os.path.abspath(__file__)))
        self.programDir = Path('%s/jamSplitter' % self.thisScriptPath.resolve())
        self.sourceDir = None
        self.targetDir = None
        self.tempDir = None
        self.maxWorkers = 1
        self.jamSession = JamSession()
        self.allMusicianShorties = None
        self.mp3Mix = {
            'isRequired': False,
            'cueSheetContent': ''
        }
        self.trackMergeRequired = False
        self.normalizeStemSplits = False
        self.normalizeTrackMergeRequired = False
        # wsp = web stem player
        self.wsp = None
        
        self.silenceDetection = None
        self.fullLengthWavMix = None
        self.fullLengthWavMixNormalized = None
        self.randomTracknames = {
            'prefixes': [],
            'suffixes': [],
            'usedTrackTitles': [],
            'usedTrackTitleWords': []
        }
        
        self.usedTracktitlesFile = None
        # TODO persist session counter n file
        self.lastSessionCounterFile = None

        self.totalDuration = 0

        self.images = [];
        self.videos = [];


class SilenceDetection(object):
    def __init__(self, activate, templateDir):
        self.templateDir = templateDir
        self.activate = activate
        self.autoDetectResultFile = None
        self.htmlTemplate = Path('%s/splitConfirm.htm' % str(self.templateDir))
        self.playerDir = Path('%s/data/stemplayer' % str(self.templateDir))
        self.jsTemplate = Path('%s/splitConfirmTemplate.js' % str(self.templateDir))
        

def main():
    global config, jamConf
    # TODO read locale from config
    locale.setlocale(locale.LC_TIME, "de_AT.UTF-8")
    
    logging.basicConfig(level=logging.WARNING)
    jamConf = JamConf()
    if not jamConf.programDir.exists():
        logging.critical('programDir \'%s\' does not exist', jamConf.programDir.resolve())

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i',
        required=True,
        type=Path,
        help='specifies the input directory with your session music files'
    )

    args = parser.parse_args()
    jamConf.sourceDir = args.i
    if not jamConf.sourceDir.is_dir():
        msg = "input directory \'%s\' does not exist" % jamConf.sourceDir.resolve()
        raise argparse.ArgumentTypeError(msg)


    config = configparser.ConfigParser(strict=False)
    configFiles = [ '%s/jamSplitter.conf' % jamConf.programDir.resolve() ]

    # optional gitignored local configuration
    localConfig = Path( '%s/jamSplitter.local.conf' % jamConf.programDir.resolve() )
    if localConfig.is_file():
        configFiles.append(localConfig.resolve())

    # optional config in source directory with audio files
    sourceDirConfig = Path( '%s/config.txt' % jamConf.sourceDir.resolve() )
    if sourceDirConfig.is_file():
        configFiles.append(sourceDirConfig.resolve())

    try:
        config.read(configFiles)
    except configparser.ParsingError as parsingError:
        print ( 'parsing error %s' % str(parsingError) )

    # TODO given arguments have highest priority override conf values again...

    if validateConfig() != True:
        print ( colored ( "exiting due to config errors...", "red" ) )
        sys.exit()
  
    #for i in range(20):
    #   print( getRandomTrackName() )
    #sys.exit()
  

    if jamConf.mp3Mix['isRequired'] == True:
        createFullLenghtWavMix()
    
    runSilenceDetection()
    
    if len(jamConf.jamSession.tracks) == 0:
        print ("no splits. nothing to do...")
   
    printCurrentSplitConfig()
    
    usedTrackTitles = []
    if jamConf.maxWorkers == 1:
        # non parallelized version
        for track in jamConf.jamSession.tracks:
            processTrack(track)
            usedTrackTitles.append(track.trackTitle)
    else:
        # paralellized tryout
        with concurrent.futures.ProcessPoolExecutor(max_workers=jamConf.maxWorkers) as executor:
            for trackIdx,track in enumerate(jamConf.jamSession.tracks):
                processedTrack = executor.submit(processTrack, (track))
                processedTrack.add_done_callback(trackProcessorCallback)
                usedTrackTitles.append(track.trackTitle)


    if config.get('enable', 'webstemplayer') == '1':
        finishWebStemSession()
        
    # TODO parse debug conf for non removal of temp files
    print (" removing temp files %s" % str(jamConf.tempDir) )
    rmtree(jamConf.tempDir)
    
    persistUsedTrackTitles(usedTrackTitles)
    persistSessionCounter()
    
    
    print ( 'EXIT in __main__' )
    sys.exit()

def persistUsedTrackTitles(usedTrackTitles):
    if jamConf.usedTracktitlesFile == None:
        return
    jamConf.usedTracktitlesFile.write_text(
        '\n'.join(getFileContent(jamConf.usedTracktitlesFile).split('\n') + usedTrackTitles)
    )

def persistSessionCounter():
    if jamConf.lastSessionCounterFile == None:
        return
    jamConf.lastSessionCounterFile.write_text(
        str(jamConf.jamSession.counter)
    )

def trackProcessorCallback(processedTrack):
    global jamConf
    processedTrack = processedTrack.result()
    for trackIdx,track in enumerate(jamConf.jamSession.tracks):
        if processedTrack.trackLetter == track.trackLetter:
            jamConf.jamSession.tracks[trackIdx] = processedTrack
    

def runSilenceDetection():
    global jamConf
    if not jamConf.silenceDetection.activate:
        return
   
    # TODO replace symlinks with hardcopies
    #copyfile(str(jamConf.silenceDetection.htmlTemplate), '%s/splitConfirm.htm' % str(jamConf.tempDir))
    #copytree(str(jamConf.silenceDetection.playerDir), '%s/stemplayer' % str(jamConf.tempDir))

    symlink(
        '../../webStemPlayer/data',
        ('%s/data' % str(jamConf.tempDir))
    )
    symlink(
        '../../webStemPlayer/splitConfirm.htm',
        ('%s/splitConfirm.htm' % str(jamConf.tempDir) )
    )

    # check if we already have a silence detection result
    if jamConf.silenceDetection.autoDetectResultFile.is_file():
        silenceDetectResultToConfigFile()
        return

    # check if we already have a merged mixdown to detect silences
    if not jamConf.fullLengthWavMix.is_file():
        _doing('create full length mixdown')
        createFullLenghtWavMix()
        

        
        _done()
    mixPeakFile = Path('%s.peaks.txt' % jamConf.fullLengthWavMix)
    if not mixPeakFile.is_file():
        wavPeaks = extractWavPeaks(
            ('%s/scripts/wavPeaks.php' % jamConf.programDir),
            jamConf.fullLengthWavMix,
            20000
        )
        mixPeakFile.write_text('\n'.join(wavPeaks))
    else:
        wavPeaks = getFileContent(mixPeakFile).split('\n')
        
    #print(wavPeaks)
    # detect silence of mix and create track boundries based on result
    _doing('detecting split points')
    silences = detectSilences(jamConf.fullLengthWavMix)
    jamConf.totalDuration = detectDuration( jamConf.fullLengthWavMix )    
    suggestedTracks = silenceDetectResultToTrackBoundries(silences, jamConf.totalDuration, 1.25, 6)

    
    jamConf.silenceDetection.autoDetectResultFile.write_text('\n'.join(suggestedTracks))
    
    # create javascript file for split confirmation
    splitConfirmJsTemplate = getFileContent(str(jamConf.silenceDetection.jsTemplate))
    
    searchReplace = {
        '{mix.peaks}': lineBreakedJoin(wavPeaks, ','),
        '{mix.duration}': jamConf.totalDuration
    }
    for search in searchReplace:
        splitConfirmJsTemplate = splitConfirmJsTemplate.replace(search, str(searchReplace[search]))

    
    splitConfirmJsFile = Path('%s/splitConfirmConf.js' % jamConf.tempDir)
    splitConfirmJsFile.write_text(splitConfirmJsTemplate)
    
    silenceDetectResultToConfigFile()

def silenceDetectResultToConfigFile():
    print ( ' silenceDetectResultToConfigFile')
    splitConfToTracks(getFileContent(jamConf.silenceDetection.autoDetectResultFile).split('\n'))
    
    while True:
        char = input()
        if char == 'r':
            splitConfToTracks(getFileContent(jamConf.silenceDetection.autoDetectResultFile).split('\n'))
            printCurrentSplitConfig()
        if char == 'y':
            break
    print ('you pressed %s'% char)
    sys.exit()

def printCurrentSplitConfig():
    global jamConf
    for track in jamConf.jamSession.tracks:
        print ('track %s %s - %s [ %s ] %s' % (
            track.trackLetter,
            secondsToMinutes(track.startSecond),
            secondsToMinutes(track.endSecond),
            secondsToMinutes(track.duration, True),
            track.trackTitle
        ))
    #sys.exit()

def _doing(term, newLine=False):
    print( colored( '  %s' % term , 'white'), end='', flush=True )
    _newLine(newLine)

def _yes(newLine=False):
    print( colored( ' YES' , 'green'), end='', flush=True )
    _newLine(newLine)

def _no(newLine=False):
    print( colored( ' NO' , 'green'), end='', flush=True )
    _newLine(newLine)

def _done(newLine=False, override=''):
    word = ' DONE' if override == '' else (' %s' % override)
    print( colored( word, 'green'), end='', flush=True )
    _newLine(newLine)

def _newLine(newLine):
    if not newLine:
        return
    print('')

def _nextTrack(track):
    # TODO add trackcounter and time
    # processing track (3/12) I - Kerouac Bondage (12:33)
    print(
        colored(
            "processing track %s/%s: %s - %s [%s]" %
            (track.trackNumber, str(len(jamConf.jamSession.tracks)), track.trackLetter, track.trackTitle, time.strftime("%M:%S", time.gmtime(track.duration)) ),
            'yellow'
        )
    )

def _nextStem(stem):
    _nextSection('checking stem', stem.uniqueStemName)
    
def _nextSection(term1, term2):
    print( colored( ' %s' % term1, 'white'), end='', flush=True )
    print( colored( ' \'%s\'' % term2, 'magenta') )

def processTrack(track):
    global jamConf
    
    # TODO benchmark split for each track vs. split within a single ffmpeg command
    _nextTrack(track)
    splitsForMergedSum = []
    
    webStemTargetDir = Path('%s/data/%s/data/%s/data' % (
        jamConf.wsp.targetDir,
        jamConf.jamSession.dirName,
        track.dirName
    ))
    track.webStemConfigJsFile = Path('%s/config.js' % str(webStemTargetDir))
    track.tracklistJsFile = Path('%s/tracklist.js' % str(webStemTargetDir))
    
    wavSplitTrackDir = Path('%s/%s/%s-wavsplits/%s-%s' % (
        jamConf.targetDir,
        jamConf.jamSession.dirName,
        jamConf.jamSession.dirName,
        track.trackLetter,
        track.trackTitle
    ))

    # create a wav split of track for all inputs
    for inputStem in jamConf.jamSession.inputFiles:
        _nextStem(inputStem)
        _doing('too short?')
        if inputStem.duration < track.startSecond:
            _yes()
            logging.info("skipping stem split (input file shorter than track start)")
            _doing('skipping...', True)
            continue

        _no()
        wavSplitIsSilence = False
        wavSplitNeedsAppendedSilence = 0
        startSecond = track.startSecond
        endSecond = track.endSecond
        _doing('append silence?')
        if inputStem.duration < track.endSecond:
            _yes()
            wavSplitNeedsAppendedSilence = track.endSecond - inputStem.duration
            logging.info("we need to append %s seconds of silence" % wavSplitNeedsAppendedSilence)
            endSecond = inputStem.duration
            
        else:
            _no()
        # split out the portion we need
        splittedWavPath = Path("%s/track_%s_wavsplit_of_stem_%s.wav" % (str(jamConf.tempDir), track.trackNumberPaddedZero, inputStem.uniqueStemName))
        _doing('splitting...')
        createWavSplit(str(inputStem.path), str(splittedWavPath), startSecond, endSecond)
        _done()

        # check if we have produced skipable silence files
        _doing('split is silence?')
        isSilenceSplit = isSilenceFile(str(splittedWavPath), endSecond - startSecond)
        if isSilenceSplit:
            _yes()
            splittedWavPath.unlink()
            _doing('skipping...', True)
            continue;
        _no()

        
        if wavSplitNeedsAppendedSilence > 0:
            # create silence and append it to wav split
            _doing('create %ss silence and merge...' % "{:.2f}".format(wavSplitNeedsAppendedSilence))
            appendSilenceToWav(str(splittedWavPath), ('%s.concatenated.wav' % str(splittedWavPath)),  str(wavSplitNeedsAppendedSilence))
            _done()
            splittedWavPath = Path('%s.concatenated.wav' % str(splittedWavPath))
        
        splitsForMergedSum.append(str(splittedWavPath))
        
        # TODO persist normalization result JSON
        _doing('normalize?')
        if jamConf.normalizeStemSplits == False:
            _no()
        else:
            _yes()
            _doing('normalize...')
            splittedWavPathNormalized = Path('%s.normalized.wav' % str(splittedWavPath))
            normalizeWav(str(splittedWavPath), str(splittedWavPathNormalized))
            #if 'skipped' in normalizeJSON:
            #    _done(False, 'SKIPPED')
            #else:
            #    _done()
            _done()
                
            #print (normalizeJSON)
        
        if config.get('webstemplayer', 'normalize') == '1':
            webStem = Stem(Path(str(splittedWavPathNormalized)))
            webStem.normLevels['vanilla'] = detectVolume( str(splittedWavPath) )
            webStem.normLevels['normalized'] = detectVolume( str(splittedWavPathNormalized) )
            track = collectTrackdbLevelBoundriesInputFiles(track, webStem.normLevels['vanilla'])
        else:
            webStem = Stem(Path(str(splittedWavPath)))
        
        webStem.byteSize = inputStem.path.stat().st_size
        webStem.uniqueStemName = inputStem.uniqueStemName
        webStem.originalName = inputStem.originalName
        webStem.musicianShorty = inputStem.musicianShorty
        webStem.duration = "{:.2f}".format(endSecond - startSecond)
        webStem.sorting = getNumericDictIndex(inputStem.musicianShorty, jamConf.allMusicianShorties) * len(jamConf.jamSession.inputFiles)
        webStem.color = inputStem.color
        
        
        if config.get('enable', 'wavSplits') == '1':
            wavSplitSource = splittedWavPathNormalized if config.get('wavsplits', 'normalize') == '1' else splittedWavPath
            wavSplitTrackDir.mkdir(parents=True, exist_ok=True)
            copyfile(str(wavSplitSource), ('%s/%s.wav'% (str(wavSplitTrackDir), inputStem.uniqueStemName)))
        
        _doing('webStemMp3?')
        if config.get('enable', 'webStemPlayer') != '1':
            _no()
        else:
            _yes()
            webStemTargetDir.mkdir(parents=True, exist_ok=True)
            webStemSource = splittedWavPathNormalized if config.get('webstemplayer', 'normalize') == '1' else splittedWavPath
            webStemTargetFile = Path('%s/%s.mp3' % ( str(webStemTargetDir), inputStem.uniqueStemName))
            _doing('wav->mp3...')
            convertWavToMp3(
                webStemSource,
                webStemTargetFile,
                config.get('webstemplayer', 'bitrate'),
                track
            )
            _done()
            _doing('extract wav peaks...')
            webStem.wavPeaks = extractWavPeaks(
                ('%s/scripts/wavPeaks.php' % jamConf.programDir),
                webStemSource,
                config.get('webstemplayer', 'waveFormResolution')
            )

            # shorten absolute path to relative path
            #webStem.path = str(webStemTargetFile)[(len(str(jamConf.wsp.targetDir))+1):]
            webStem.path = str(webStemTargetFile.name)
            track.stems.append(webStem)
            track.byteSize = track.byteSize + webStem.byteSize
            _done()
            #print(wavPeaks)
        _newLine(True)
            

    if not len(splitsForMergedSum):
        print ( colored ("WARNING: all stems seems to be silence. skipping track...", 'red'), flush=True )
        # TODO we have to decrement letters and tracknumbers, right?
        # but this will be tricky with parallel processTrack execution...
        return
  

    _nextSection('sum of', 'all stems')
    _doing('need merge?')
    if jamConf.trackMergeRequired == False:
        _no()
    else:
        _yes()
        trackMergedSumPath = Path("%s/track_%s_merged_not_normalized.wav" % (str(jamConf.tempDir), track.trackNumberPaddedZero) )
        _doing('merging...')
        mergeInputWavsToSingleFile(splitsForMergedSum, str(trackMergedSumPath))
        _done()
    
        trackMergedSumPathNormalized = Path("%s/track_%s_merged_normalized.wav" % (str(jamConf.tempDir), track.trackNumberPaddedZero) )
        _doing('normalize?')
        if jamConf.normalizeTrackMergeRequired == False:
            _no()
        else:
            _yes()
            _doing('normalize...')
            normalizeWav(str(trackMergedSumPath), str(trackMergedSumPathNormalized))
            _done()
    
        _doing('BPM detect?')
        if config.get('enable', 'bpmDetect') != '1':
            _no()
        else:
            _yes()
            _doing('detecting BPM...')
            track.bpm = detectBpm(str(trackMergedSumPath), config.get('bpmdetect', 'method'))
            _done(False, track.bpm)
    
    _doing('mp3 splits?')
    if config.get('enable', 'mp3splits') != '1':
        _no()
    else:
        _yes()
        wavSplitSource = trackMergedSumPathNormalized if config.get('mp3splits', 'normalize') == '1' else trackMergedSumPath
        mp3SplitTrackDir = Path('%s/%s/%s-mp3splits/' % (
            jamConf.targetDir,
            jamConf.jamSession.dirName,
            jamConf.jamSession.dirName
        ))
        mp3SplitTrackPath = Path('%s/%s-%s.mp3' % ( str(mp3SplitTrackDir), track.trackLetter, track.trackTitle))
        mp3SplitTrackDir.mkdir(parents=True, exist_ok=True)
        mp3SplitBitrate = config.get('mp3splits', 'bitrate')
        _doing('wav->mp3...')
        convertWavToMp3(str(wavSplitSource), str(mp3SplitTrackPath), mp3SplitBitrate, track)
        _done()

    _doing('webStemMp3?')
    if config.get('enable', 'webStemPlayer') != '1':
        _no()
    else:
        _yes()
        # create symlinks for single track
        symlink(
            '../../../../stemplayer',
            ('%s/stemplayer' % str(webStemTargetDir))
        )
        symlink(
            ('../../../../%s' % jamConf.wsp.baseHtmlName),
            ('%s/../%s.htm' % (str(webStemTargetDir), az09(track.trackTitle)) )
        )
        
        finishWebStemTrack(track)
        _done()
        #print(wavPeaks)
    _newLine(True)
    return track

def finishWebStemTrack(track):
    global jamConf
    
    
    imagesJs = []
    for image in jamConf.images:
        imageJsTemplate = getFileContent(str(jamConf.wsp.imageConfigTemplate))
        searchReplace = {
            '{image.path}': str(image.newFileName),
            '{image.byteSize}': str(image.byteSize),
            '{image.thumbPath}': str(image.thumbTargetPath)
        }
        for search in searchReplace:
            imageJsTemplate = imageJsTemplate.replace(search, str(searchReplace[search]))
        imagesJs.append(imageJsTemplate)

    videosJs = []
    for video in jamConf.videos:
        videoJsTemplate = getFileContent(str(jamConf.wsp.videoConfigTemplate))
        searchReplace = {
            '{video.path}': str(video.newFileName),
            '{video.byteSize}': str(video.byteSize),
            '{video.stillPath}': str(video.stillTargetPath),
            '{video.thumbPath}': str(video.thumbTargetPath)
        }
        for search in searchReplace:
            videoJsTemplate = videoJsTemplate.replace(search, str(searchReplace[search]))
        videosJs.append(videoJsTemplate)

    stemsJs = []
    # we need a very special weighted sorting...
    for stem in sortStems(track.stems):
        stemJsTemplate = getFileContent(str(jamConf.wsp.stemConfigTemplate))
        searchReplace = {
            '{stem.path}': str(stem.path),
            '{stem.peaks}': lineBreakedJoin(stem.wavPeaks, ','),
            '{stem.title}': stem.originalName,
            '{stem.volume}': guessInitalVolumeLevel(stem.normLevels, track.dbLevelsInputFiles),
            '{stem.color}': stem.color,
            '{stem.normalizationLevels}': json.dumps(stem.normLevels),
            '{stem.byteSize}': str(stem.byteSize)
        }
        for search in searchReplace:
            stemJsTemplate = stemJsTemplate.replace(search, str(searchReplace[search]))

        stemsJs.append(stemJsTemplate)
    trackJsTemplate = getFileContent(str(jamConf.wsp.trackConfigTemplate))
    searchReplace = {
        '{session.counter}': jamConf.jamSession.counter,
        '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
        '{session.date}': jamConf.jamSession.dateString,
        '{session.day}': jamConf.jamSession.day,
        '{session.month}': jamConf.jamSession.month,
        '{session.year}': jamConf.jamSession.year,
        '{track.letter}': track.trackLetter,
        '{track.number}': track.trackNumber,
        '{track.title}': track.trackTitle,
        '{track.artist}': track.artist,
        '{track.genre}': track.genre,
        '{track.duration}': track.duration,
        '{track.byteSize}': str(track.byteSize),
        '{track.bpm}': track.bpm,
        '{track.splitStart}': track.startSecond,
        '{track.splitEnd}': track.endSecond,
        '{track.dbLevelsInputFiles}': track.dbLevelsInputFiles,
        '{stems}': ','.join(stemsJs),
        '{images}': ','.join(imagesJs),
        '{videos}': ','.join(videosJs)
    }
    for search in searchReplace:
        trackJsTemplate = trackJsTemplate.replace(search, str(searchReplace[search]))

    track.webStemConfigJsFile.write_text(trackJsTemplate)
    #print(trackJsTemplate)

''' make editors with a 4096 characters per line limit happy'''
def lineBreakedJoin(media_list, joinChar):
    nthItem = 45
    listLines = [joinChar.join(media_list[nthItem * i: nthItem * i + nthItem]) for i in range(0, int(len(media_list) / nthItem))]
    return ('%s\n                  ' % joinChar).join(listLines)

def guessInitalVolumeLevel(stemLevels, trackLevelBoundries):
    stemMeanValue = float(stemLevels['vanilla']['mean_volume']);
    foundMax = float(trackLevelBoundries['meanVolumeMax']);
    foundMin = float(trackLevelBoundries['meanVolumeMin']);
    foundMin = -50

    targetMax = 1;
    targetMin = 0.2;
    
    onePercent = (foundMin*-1) - (foundMax*-1);
    targetPercent = 1 - (((stemMeanValue*-1) - (foundMax*-1)) / onePercent) * (targetMax - targetMin);
    if targetPercent < targetMin:
        return targetMin
    return targetPercent

def finishWebStemSession():
    global jamConf
    
    
    trackJsTemplate = '        { trackIndex : "{track.trackLetter}", trackDir: "{track.dirName}" }'
    tracklistJsTemplate = getFileContent(str(jamConf.wsp.tracklistConfigTemplate))
    allTracksJs = []
    
    for track in jamConf.jamSession.tracks:
        searchReplace = {
            '{track.dirName}': track.dirName,
            '{track.trackLetter}': track.trackLetter
        }
        trackJs = trackJsTemplate
        for search in searchReplace:
            trackJs = trackJs.replace(search, str(searchReplace[search]))

        allTracksJs.append(trackJs)
        
        # create single config in trackdirectory
        singleTrackJs = tracklistJsTemplate
        searchReplace = {
            '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
            '{session.dirName}': jamConf.jamSession.dirName,
            '{trackItems}': trackJs,
            '{hostLevel}': 'track'
        }
        for search in searchReplace:
            singleTrackJs = singleTrackJs.replace(search, str(searchReplace[search]))

        track.tracklistJsFile.write_text(singleTrackJs)
    
    
    # create another config in sessions directory
    trackJs = tracklistJsTemplate
    searchReplace = {
        '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
        '{session.dirName}': jamConf.jamSession.dirName,
        '{trackItems}': ',\n'.join(allTracksJs),
        '{hostLevel}': 'tracklist'
    }
    for search in searchReplace:
        trackJs = trackJs.replace(search, str(searchReplace[search]))

    tracklistJsFile = Path('%s/data/%s/data/tracklist.js' % (
        jamConf.wsp.targetDir,
        jamConf.jamSession.dirName
    ))
    
    tracklistJsFile.write_text(trackJs)
    

    # create stemplayer symlink and the html document symlink for single session    
    symlink(
        '../../stemplayer',
        ('%s/data/%s/data/stemplayer' % ( str(jamConf.wsp.targetDir), jamConf.jamSession.dirName) )
    )
    symlink(
        ('../../%s' % jamConf.wsp.baseHtmlName),
        ('%s/data/%s/%s.htm' % (str(jamConf.wsp.targetDir), jamConf.jamSession.dirName, az09(jamConf.jamSession.dirName)) )
    )
    
    
    
    # create another config for all sessions to append
    trackJs = tracklistJsTemplate
    searchReplace = {
        '{session.paddedCounter}': jamConf.jamSession.paddedCounter,
        '{session.dirName}': jamConf.jamSession.dirName,
        '{trackItems}': ',\n'.join(allTracksJs),
        '{hostLevel}': 'sessionlist'
    }
    for search in searchReplace:
        trackJs = trackJs.replace(search, str(searchReplace[search]))

    sessionlistJsFile = Path('%s/data/tracklist.js' % jamConf.wsp.targetDir)
    # in case it already exist we have to inject to the beginning of the file
    if sessionlistJsFile.is_file():
        trackJs = trackJs + getFileContent(str(sessionlistJsFile))
    
    sessionlistJsFile.write_text(trackJs)


    # copy images
    imagesTargetDir = Path('%s/data/%s/data/images' % (
        jamConf.wsp.targetDir,
        jamConf.jamSession.dirName
    ))
    for image in jamConf.images:
        imagesTargetDir.mkdir(parents=True, exist_ok=True)
        sourcePath = str(image.path)
        targetPath = ('%s/../../%s'% (str(imagesTargetDir), image.newFileName))
        copyfile(sourcePath, targetPath)

        # create thumbnails
        # TODO enable/disable via config
        # TODO move dimensions to config
        size = (160, 160)
        thumbSource = Image.open(sourcePath)
        thumbTarget = ImageOps.fit(thumbSource, size, Image.ANTIALIAS)
        thumbTarget.save(('%s/../../%s'% (str(imagesTargetDir), image.thumbTargetPath)))


    # copy videos
    videosTargetDir = Path('%s/data/%s/data/videos' % (
        jamConf.wsp.targetDir,
        jamConf.jamSession.dirName
    ))
    for video in jamConf.videos:
        videosTargetDir.mkdir(parents=True, exist_ok=True)
        sourcePath = str(video.path)
        targetPath = ('%s/../../%s'% (str(videosTargetDir), video.newFileName))
        copyfile(sourcePath, targetPath)

        # extract video frame
        stillTargetPath = ('%s/../../%s'% (str(videosTargetDir), video.stillTargetPath))
        captureVideoFrame(sourcePath, stillTargetPath )

        # create thumbnails
        # TODO enable/disable via config
        # TODO move dimensions to config
        size = (160, 160)
        thumbSource = Image.open(stillTargetPath)
        thumbTarget = ImageOps.fit(thumbSource, size, Image.ANTIALIAS)
        thumbTarget.save(('%s/../../%s'% (str(imagesTargetDir), video.thumbTargetPath)))


def sortStems(stemsList):
    global jamConfig
    dictToSort = {0:[]}
    for stem in stemsList:
        if config.get('webstemplayer', 'drumsOnTop') == '1':
            if stem.uniqueStemName.find('drum') >= 0:
                dictToSort[0].append(stem)
                continue
        if not stem.sorting in dictToSort:
            dictToSort[stem.sorting] = []
        dictToSort[stem.sorting].append(stem)

    final = []
    for key in sorted(dictToSort):
        for stem in dictToSort[key]:
            final.append(stem)
            
    return final

def addMissingColorsToInputFiles():
    global jamConf
    allColors = config.get('webstemplayer', 'colors').split()
    availableColors = allColors[:]

    for inputFile in jamConf.jamSession.inputFiles:
        if inputFile.color != '' and inputFile.color in availableColors:
            availableColors.remove(inputFile.color)
    
    for i,inputFile in enumerate(jamConf.jamSession.inputFiles):
        if inputFile.color != '':
            continue
        if len(availableColors) == 0:
            availableColors = allColors[:]
        randomColor = secrets.choice(availableColors)
        jamConf.jamSession.inputFiles[i].color = randomColor
        availableColors.remove(randomColor)

            
    
def collectTrackdbLevelBoundriesInputFiles(track, volumeJSON):
    
    try:
        if float(volumeJSON['mean_volume']) < track.dbLevelsInputFiles['meanVolumeMin']:
            track.dbLevelsInputFiles['meanVolumeMin'] = float(volumeJSON['mean_volume'])
        if float(volumeJSON['mean_volume']) > track.dbLevelsInputFiles['meanVolumeMax']:
            track.dbLevelsInputFiles['meanVolumeMax'] = float(volumeJSON['mean_volume'])
        if float(volumeJSON['max_volume']) < track.dbLevelsInputFiles['maxVolumeMin']:
            track.dbLevelsInputFiles['maxVolumeMin'] = float(volumeJSON['max_volume'])
        if float(volumeJSON['max_volume']) > track.dbLevelsInputFiles['maxVolumeMax']:
            track.dbLevelsInputFiles['maxVolumeMax'] = float(volumeJSON['max_volume'])
    except KeyError:
        return track
    return track

def getAllMusicianShorties():
    global config
    unique = {}
    for key,val in config.items("musicians"):
        shorty = key.split('.')
        unique[shorty[0]] = shorty[0]

    return unique

def getNumericDictIndex(keyToSearch, dictToSearch):
    idx = 1
    for key in dictToSearch:
        if key == keyToSearch:
            return idx
        idx += 1
    return 0

def getConfigPath(confSection, confName):
    global jamConf
    return config.get(confSection, confName).replace('{SCRIPT_PATH}', str(jamConf.programDir))

def validateConfig():
    global config, jamConf
    jamConf.allMusicianShorties = getAllMusicianShorties()
    inputFiles = searchAudioSourceFiles()
    if len(inputFiles) == 0:
        logging.error('no audio files in directory \'%s\' found...' % jamConf.sourceDir)
        return False

    stemFilesNames = {}
    foundShorties = []
    for inputFile in inputFiles:
        inputFileMeta = InputFile(inputFile)
        inputFileMeta.originalName = inputFile.stem
        newName = az09(inputFile.stem, '', True)
        for shorty in jamConf.allMusicianShorties:
            pattern = ".*"+config.get( 'musicians', shorty+'.pattern' )+".*"
            if pattern == ".**.*":
                pattern = ".*"
            #print ( "shorty: %s, pattern: %s" % (shorty, pattern) )
            # TODO john vs. johnny may gives invalid sorting when first match is shorter
            if re.search(pattern+"", newName):
                foundShorties += [shorty]
                inputFileMeta.musicianShorty = shorty
                try:
                    inputFileMeta.color = config.get('musicians', '%s.color' % shorty)
                except configparser.NoOptionError:
                    inputFileMeta.color = ''
                
                break
            #print ( "pattern: %s" % pattern )

        # append number suffix in case we have identical filenames in different subdirectories
        newName = getUniqueName( newName, stemFilesNames)

        stemFilesNames[ inputFile.resolve() ] = newName
        inputFileMeta.uniqueStemName = newName
        #print ( "inputFile: %s" % inputFile.stem )
        #print (foundShorties)

        # detect duration of input file
        inputFileMeta.duration = detectDuration(str(inputFile))
        
        # persist longest duration (need for possible concatenation with silence wavs)
        if inputFileMeta.duration > jamConf.jamSession.duration:
            jamConf.jamSession.duration = inputFileMeta.duration
        
        
        
        
        
        jamConf.jamSession.inputFiles.append(inputFileMeta)

    jamConf.jamSession.uniqueSortedShorties = sortByPriority( foundShorties, jamConf.allMusicianShorties, True)
    
    # make sure the use same random color for all tracks within this session
    addMissingColorsToInputFiles()

    # TODO read fallback counter by increment last counter from previous session
    # parse counter and add padded zeroes in case it starts with a number
    # example inputs "4" "0004" "000005.2" "5 part 2" "Custom Session Counter #66"
    rawCounterInput = config.get('general', 'counter')
    if not rawCounterInput:
        msg = "no session counter given"
        raise argparse.ArgumentTypeError(msg)
        return False

    counterPadding = config.get('general', 'counterPadding', fallback='3')
    if rawCounterInput.isnumeric():
        counter = str(int(rawCounterInput))
        paddedCounter = ("%0" + counterPadding + "d" )%int(counter)
    else:
        # lets see if the first captured group is numeric
        match = re.match('^([0-9]{1,20})([^0-9]{1,})(.*)$', rawCounterInput)
        if match:
            trailingNumbers = match.group(1)
            counter = str(int(trailingNumbers)) + match.group(2) + match.group(3)
            paddedCounter = ("%0" + counterPadding + "d" )%int(trailingNumbers) + match.group(2) + match.group(3)
        else:
            counter = rawCounterInput
            paddedCounter = rawCounterInput

    #print (" >%s< >%s<" % (counter, paddedCounter))
    jamConf.jamSession.counter = counter
    jamConf.jamSession.paddedCounter = paddedCounter
    
    # parse date string
    dateString = config.get('general', 'sessiondate', fallback=str(datetime.datetime.now().year))
    pattern = "(\d{4})\.?(\d{1,2})?\.?(\d{1,2})?"
    match = re.match( pattern, dateString)
    if match:
        jamConf.jamSession.day = ("%02d" )%int(match.group(3))  if match.group(3) else '??'
        jamConf.jamSession.month = datetime.date(1900, int(match.group(2)), 1).strftime('%b') if match.group(2)  else '???'
        jamConf.jamSession.year = match.group(1) if match.group(1)  else '????'

    jamConf.jamSession.dateString = dateString

    jamConf.jamSession.dirName = config.get( 'general', 'dirScheme' ) \
        .replace( '{bandname}', config.get('general', 'bandname') ) \
        .replace( '{padded_counter}', jamConf.jamSession.paddedCounter ) \
        .replace( '{counter}', jamConf.jamSession.counter ) \
        .replace( '{date}', jamConf.jamSession.dateString ) \
        .replace( '{shorties}', '-'.join(jamConf.jamSession.uniqueSortedShorties) )
    
    if config.get('general', 'noSpecialChars') == '1':
        jamConf.jamSession.dirName = az09(jamConf.jamSession.dirName)
        
    jamConf.targetDir = Path(getConfigPath('general', 'targetDir') )
    if not jamConf.targetDir.is_dir():
        msg = "target directory \'%s\' does not exist" % jamConf.targetDir.resolve()
        raise argparse.ArgumentTypeError(msg)
        return False

    # to use unique temp directory we create a hidden file in sourceDir
    tempDirNameFile = Path('%s/.tempdir' % str(jamConf.sourceDir))
    if not tempDirNameFile.is_file():
        tempHash = hashlib.md5(str(jamConf.sourceDir).encode('utf-8')).hexdigest()[:6]
        tempDirNameFile.write_text(tempHash)
    else:
        tempHash = getFileContent(tempDirNameFile).split()[0]
    
    jamConf.tempDir = Path('%s/temp-%s' % (str(jamConf.targetDir), tempHash))
    jamConf.tempDir.mkdir(parents=True, exist_ok=True)
    
    jamConf.fullLengthWavMix = Path("%s/full_length_mix_merged_not_normalized.wav" % str(jamConf.tempDir) )
    jamConf.fullLengthWavMixNormalized = Path("%s/full_length_mix_merged_normalized.wav" % str(jamConf.tempDir) )

    maxWorkers = config.get('general', 'maxWorkers')
    if maxWorkers.isnumeric:
        jamConf.maxWorkers = int(maxWorkers)

    splitConfToTracks()

    if len(jamConf.jamSession.tracks) > 0:
        # we dont need any split detection if we have configured splits
        jamConf.silenceDetection = SilenceDetection(False, getConfigPath('silencedetect', 'templateDir'))
    else:
        # we dont need any split detection if disabled by config
        if config.get('enable', 'silenceDetect') != '1':
            jamConf.silenceDetection = SilenceDetection(False, getConfigPath('silencedetect', 'templateDir'))
        else:
            jamConf.silenceDetection = SilenceDetection(True, getConfigPath('silencedetect', 'templateDir'))
            jamConf.silenceDetection.autoDetectResultFile = Path('%s/silence_detect_result.txt' % str(jamConf.tempDir))

    if config.get('enable', 'mp3splits') == '1':
        jamConf.trackMergeRequired = True
        if config.get('mp3splits', 'normalize') == '1':
            jamConf.normalizeTrackMergeRequired = True

    if config.get('tracknames', 'useRandomTracknames') == '1':
        jamConf.usedTracktitlesFile = Path(getConfigPath('tracknames', 'usedTrackTitlesFile') )
        jamConf.usedTracktitlesFile.touch(exist_ok=True)

    jamConf.lastSessionCounterFile = Path(getConfigPath('general', 'lastSessionCounterFile') )
    jamConf.lastSessionCounterFile.touch(exist_ok=True)

    if config.get('enable', 'bpmDetect') == '1':
        jamConf.trackMergeRequired = True
    
    if config.get('enable', 'stems') == '1':
        jamConf.trackMergeRequired = True
        if config.get('stem', 'normalizeSum') == '1':
            jamConf.normalizeTrackMergeRequired = True
        if config.get('stem', 'normalizeStems') == '1':
            jamConf.normalizeStemSplits = True

    if config.get('enable', 'webStemPlayer') == '1':
        if config.get('webstemplayer', 'normalize') == '1':
            jamConf.normalizeStemSplits = True

        wsp = WebStemPlayer(Path(getConfigPath('webstemplayer', 'templateDir')))
        if not wsp.templateDir.is_dir():
            print( colored ( "webStemPlayer template directory \'%s\' does not exist" % str(wsp.templateDir), "red" ) )
            return False
        if not wsp.playerDir.is_dir():
            print( colored ( "player template directory \'%s\' does not exist" % str(wsp.playerDir), "red" ) )
            return False
        if not wsp.htmlTemplate.is_file():
            print( colored ( "player html template file \'%s\' does not exist" % str(wsp.htmlTemplate), "red" ) )
            return False
        if not wsp.trackConfigTemplate.is_file():
            print( colored ( "player track template file \'%s\' does not exist" % str(wsp.trackConfigTemplate), "red" ) )
            return False
        if not wsp.stemConfigTemplate.is_file():
            print( colored ( "player stem template file \'%s\' does not exist" % str(wsp.stemConfigTemplate), "red" ) )
            return False
        if not wsp.tracklistConfigTemplate.is_file():
            print( colored ( "player tracklist template file \'%s\' does not exist" % str(wsp.tracklistConfigTemplate), "red" ) )
            return False
        wsp.targetDir = Path(getConfigPath('webstemplayer', 'targetDir'))
        if not wsp.targetDir.is_dir():
            print( colored ( "webStemPlayer targetDir directory \'%s\' does not exist" % str(wsp.targetDir), "red" ) )
            return False
        wsp.baseHtmlName = config.get('webstemplayer', 'baseHtml')
        if wsp.baseHtmlName == '':
            wsp.baseHtmlName = '%s-All Sessions.htm' % config.get('general', 'bandname')
        wsp.baseHtml = Path( '%s/%s' % ( str(wsp.targetDir), wsp.baseHtmlName))
        
        # very first time we use webstemplayer? create base for symlink targets
        if not wsp.baseHtml.is_file():
            copyfile(str(wsp.htmlTemplate), str(wsp.baseHtml))
            
        baseStemPlayerDir = Path('%s/data/stemplayer' % str(wsp.targetDir) )
        if not baseStemPlayerDir.is_dir():
            copytree(str(wsp.playerDir), str(baseStemPlayerDir))

        jamConf.wsp = wsp

    if config.get('webstemplayer', 'includeMedia') == '1':
        jamConf.images = searchImageFiles()
        jamConf.videos = searchVideoFiles()

    return True

def getUniqueName(itemName, itemList):
    if not itemName in itemList.values():
        return itemName
    
    for i in range(1, 100):
        newName = itemName + '.' + str(i)
        if not newName in itemList.values():
            return newName
    
    # TODO how to handle this?
    return itemName

def splitConfToTracks(autoDetected = None):
    global config, jamConf
    if autoDetected == None:
        confLines = config.get('splitter', 'splitpoints').split('\n')
    else:
        confLines = autoDetected
    
    trackNumber = 1
    trackLetter = 'A'
    jamConf.jamSession.tracks = []
    for confLine in confLines:
        if confLine == '':
            continue

        pattern = "([0-9]{1,2}\:)?([0-9]{1,3})\:([0-9]{2})(\.[0-9]{0,3})?\ ?-\ ?([0-9]{1,2}\:)?([0-9]{1,3})\:([0-9]{2})(\.[0-9]{0,3})?\ ?(.*)?$"
        match = re.match( pattern, confLine)
        if not match:
            logging.warning("invalid split conf line '%s'" % confLine)

        track = Track()
        startH = int(match.group(1).replace(':', '')) if match.group(1) else 0
        startM = int(match.group(2)) if match.group(2) else 0
        startS = int(match.group(3)) if match.group(3) else 0
        startD = float("0" + str(match.group(4))) if match.group(4) else 0
        track.startSecond = 3600 * startH + 60 * startM + startS + startD

        endH = int(match.group(5).replace(':', '')) if match.group(5) else 0
        endM = int(match.group(6)) if match.group(6) else 0
        endS = int(match.group(7)) if match.group(7) else 0
        endD = float("0" + str(match.group(8))) if match.group(8) else 0
        track.endSecond = 3600 * endH + 60 * endM + endS + endD

        if track.startSecond > track.endSecond:
            # invalid config
            logging.warning("invalid split conf line (start > end) '%s'" % confLine)
            continue

        if track.endSecond > jamConf.jamSession.duration:
            # invalid config
            logging.warning("invalid split conf line (end > sessionlength) '%s'" % confLine)
            continue

        track.trackTitle = match.group(9).strip() if match.group(9) != '' else getRandomTrackName()
        track.trackLetter = trackLetter
        track.trackNumber = trackNumber
        track.trackNumberPaddedZero = ("%02d" ) % trackNumber
        track.dirName = az09( "%s%s-%s" % (jamConf.jamSession.paddedCounter, track.trackLetter, track.trackTitle) )
        
        track.duration = track.endSecond - track.startSecond
        track.artist = config.get('general', 'bandname')
        track.genre = config.get('general', 'genre')
        track.album = 'TODO: album name scheme from config (outside of for loop)'
        
        logging.info("splitConfTrack [%s - %s] %s - %s" % (track.startSecond, track.endSecond, track.trackLetter, track.trackTitle))
        
        jamConf.jamSession.tracks.append(track)
        trackNumber += 1
        trackLetter = nextLetter(trackLetter)
            


def createFullLenghtWavMix():
    global jamConf

    mixInputFilesForMerge = []
    for inputFile in jamConf.jamSession.inputFiles:
        mixInputFilesForMerge.append(str(inputFile.path.resolve()))
    
    mergeInputWavsToSingleFile( mixInputFilesForMerge, str(jamConf.fullLengthWavMix) )

    
def finishMp3Mix():
    global jamConf
    mixDownDir = Path('%s/%s/%s-mix' % (jamConf.targetDir.resolve(), jamConf.jamSession.dirName, jamConf.jamSession.dirName))
    mixDownDir.mkdir(parents=True, exist_ok=True)
    
    # TODO skip normalization of mp3mix if we need it only for silence detection....
    normalizationJSON = normalizeWav( str(jamConf.fullLengthWavMix), str(jamConf.fullLengthWavMixNormalized) )
    
    # TODO convert wav to mp3
    # TODO which tags should be written?


def searchAudioSourceFiles():
    return recusiveFindByExtList(
        jamConf.sourceDir,
        config.get('general', 'inputFileExt')
    )


def searchImageFiles():
    images = recusiveFindByExtList(
        jamConf.sourceDir,
        config.get('media', 'imagesExt')
    )
    result = []
    for item in images:
        image = ImageFile(item)
        image.dateTime = detectTimestampFromString(item.stem)
        image.byteSize = item.stat().st_size
        # keep original relative path in filename
        image.newFileName = 'data/images/' + str(item)[(len(str(jamConf.sourceDir))+1):].replace('/', '-')
        image.thumbTargetPath = image.newFileName + '.thumbnail.png'
        result.append(image)

    return result


def searchVideoFiles():
    videos = recusiveFindByExtList(
        jamConf.sourceDir,
        config.get('media', 'videosExt')
    )
    result = []
    for item in videos:
        video = VideoFile(item)
        video.dateTime = detectTimestampFromString(item.stem)
        video.byteSize = item.stat().st_size
        # keep original relative path in filename
        video.newFileName = 'data/videos/' + str(item)[(len(str(jamConf.sourceDir))+1):].replace('/', '-')
        video.thumbTargetPath = video.newFileName + '.thumbnail.png'
        video.stillTargetPath = video.newFileName + '.png'
        result.append(video)

    return result

''' it seems to be common to have filenames like YYYYMMDD_HHMMSS.jpg '''
def detectTimestampFromString(inputString):
    dateTime = None
    match = re.match('.*([0-9]{8}\_[0-9]{6}).*', inputString)
    if match:
        dateTime = datetime.datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')

    return dateTime

def recusiveFindByExtList(searchPath, extListString):
    extList = ['.' + x.strip() for x in extListString.lower().split(',')]
    foundFiles = []
    for foundFile in searchPath.rglob('*.*'):
        if foundFile.suffix.lower() in extList:
            foundFiles += [ foundFile ]

    return foundFiles

def getRandomTrackName():
    global config
    
    if len(jamConf.randomTracknames['usedTrackTitleWords']) == 0:
        jamConf.randomTracknames['usedTrackTitles'] = getFileContent(
            str(jamConf.usedTracktitlesFile)
        ).split('\n')
        jamConf.randomTracknames['usedTrackTitleWords'] = ' '.join(jamConf.randomTracknames['usedTrackTitles']).split()
    
    
    
    if len(jamConf.randomTracknames['prefixes']) == 0:
        items = removeOftenUsedListItems(
            config.get('tracknames', 'prefixes').split(),
            jamConf.randomTracknames['usedTrackTitleWords'],
            50
        )
        # remove duplicates
        jamConf.randomTracknames['prefixes'] = list(set(items))
    if len(jamConf.randomTracknames['suffixes']) == 0:
        items = removeOftenUsedListItems(
            config.get('tracknames', 'suffixes').split(),
            jamConf.randomTracknames['usedTrackTitleWords'],
            50
        )
        # remove duplicates
        jamConf.randomTracknames['suffixes'] = list(set(items))
    
    # shuffle words list
    random.shuffle(jamConf.randomTracknames['prefixes'])
    random.shuffle(jamConf.randomTracknames['suffixes'])

    # pick the first
    chosenPrefix = jamConf.randomTracknames['prefixes'][0]
    chosenSuffix = jamConf.randomTracknames['suffixes'][0]
    
    # remove chosen item to avoid duplicates
    jamConf.randomTracknames['prefixes'].remove(chosenPrefix)
    jamConf.randomTracknames['suffixes'].remove(chosenSuffix)
    
    # drop prefix or suffix sometimes
    if random.randint(1,100) > 85:
        finalTrackTitle = chosenPrefix if random.randint(1,100) < 20 else chosenSuffix
    else:
        # TODO avoid endless recursion caused by configuration quirks
        if chosenPrefix == chosenSuffix:
            return getRandomTrackName()
        finalTrackTitle = "%s %s" % (chosenPrefix, chosenSuffix)
    
    # vice versa check against ".usedTracktitles"
    if finalTrackTitle in jamConf.randomTracknames['usedTrackTitles']:
        # TODO avoid endless recursion caused by configuration quirks
        return getRandomTrackName()

    return finalTrackTitle

def removeOftenUsedListItems( allItems, usedItems, neededAmount):
    if len(allItems) < neededAmount:
        return allItems

    if len(usedItems) == 0:
        return allItems

    weighted = {}
    for item in allItems:
        for usedItem in usedItems:
            if not item in weighted:
                weighted[item] = 0
            if item == usedItem:
                weighted[item] = weighted[item] +1
                
    # group itmes by count
    groupedByCount = {}
    for key,value in sorted(enumerate(weighted), reverse=True):
        if not weighted[value] in groupedByCount:
           groupedByCount[ weighted[value] ] = []
        groupedByCount[ weighted[value] ].append(value)
    
    finalItems = []
    for key in sorted(groupedByCount.keys()):
        finalItems = finalItems + groupedByCount[key]
        if len(finalItems) >= neededAmount:
            return finalItems
            
    return finalItems
    

if __name__ == '__main__':
    main()
