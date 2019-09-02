 
import re
import os
import math

# TODO check OS and make hard copies on windows machines
def symlink(pathFrom, pathTo):
    try:
        os.symlink(pathFrom, pathTo)
    except FileExistsError:
        return

def getFileContent(pathAndFileName):
    with open(pathAndFileName, 'r') as theFile:
        data = theFile.read()
        return data
    

def secondsToMinutes(seconds, dropDecimals = False):
    minutes = '%02.1d' % ( seconds // 60 )
    if dropDecimals == False:
        remainingSeconds = '%04.1f' % (seconds % 60)
    else:
        remainingSeconds = '%02.1d' % math.floor(seconds % 60)
    return '%s:%s' % (minutes, remainingSeconds)

def nextLetter(currentLetter):
    return str(bytes([bytes(currentLetter, 'utf-8')[0] + 1]))[2]

def sortByPriority(itemsToSort, priorityStrings, removeDuplicates=False):
    #print ("sortByPriority()") 
    result = {}
    gappedArray = []
    for i in range(0, (len(priorityStrings)*len(itemsToSort))):
        #print(i)
        #gappedArray[i] = 0
        gappedArray.insert(i,0)
    
    #print(gappedArray)
    itemStringCounter=-1
    for itemString in itemsToSort:
        ++itemStringCounter
        #print ( "itemString: %s" % itemString )
        prioStringCounter=-1
        for prioString in priorityStrings:
            prioStringCounter = prioStringCounter + 1
            #print( "prioStringCounter %s" % prioStringCounter)
            weightedStartKey = prioStringCounter*len(itemsToSort)
            #print ( "prioString: %s" % prioString )
            if prioString == itemString:
                #print ("FOUND: %s" % prioString)
                if gappedArray[weightedStartKey] == 0:
                    #print( "weightedStartKey %s is FREE" % weightedStartKey)
                    gappedArray[weightedStartKey] = itemString
                    break
                #print( "weightedStartKey %s in use" % weightedStartKey)
                for newIndex in range(weightedStartKey, len(gappedArray)):
                    if gappedArray[newIndex] == 0:
                        gappedArray[newIndex] = itemString
                        break;
        #print ( itemString )
        
    finalArray = []
    for val in gappedArray:
        if val == 0:
            continue
        if removeDuplicates == False:
            finalArray += [val]
            continue
        if val in finalArray:
            continue
        finalArray += [val]
    #print( itemToSort )
    #print (finalArray)
    return finalArray


''' parse the result and format it to trackStart - trackEnd\n'''
''' TODO: use result of silenceDetectResultToSilenceBoundries() as a basis'''
def silenceDetectResultToTrackBoundries(resultLines, totalDuration, silencePadding = 1.25, dontSplitTreshold = 6):
 
    suggestedTracks = []
    previousEnd = 0
    currentStart = 0
    currentEnd = 0
    currentDuration = 0
    foundTrackStart = 0
    foundTrackEnd = 0
    beginsWithSilence = False
    silenceShift = False
    silenceUntilEnd = False

    splittedSilence = resultLines.split('\n')
    for line in splittedSilence:
        if line.find('silencedetect') < 0:
            continue

        lineArgs = line.strip().split()
        
        # TODO: unexplainable list modification with some stdout stuff which should be skipped by condition above
        # sometimes we need to remove the first few list items to can relay on the indices
        for idx,arg in enumerate(lineArgs):
            if arg == '[silencedetect':
                lineArgs = lineArgs[idx:]
                break

        if line.find('silence_start') >= 0:
            currentStart = float(lineArgs[4])
            # check if we start with a silence
            if currentStart < 1:
                beginsWithSilence = True
            silenceUntilEnd = True
        
        
        if line.find('silence_end') >= 0 or line.find('silence_duration') >= 0:
            silenceUntilEnd = False
            
            currentEnd = float(lineArgs[4])
            currentDuration = float(lineArgs[7])
            
            if beginsWithSilence == True and silenceShift == False:
                foundTrackStart = currentEnd - silencePadding
                previousEnd = currentEnd
                silenceShift = True
                continue

            # skip very short tracks 
            nextTrackDuration = currentStart - previousEnd
            if nextTrackDuration > 0 and nextTrackDuration < dontSplitTreshold:
                #logging.info( 'skipping silence based track match. %s seems to be too short' % nextTrackDuration )
                previousEnd = currentEnd
                continue

            foundTrackStart = previousEnd - silencePadding
            if foundTrackStart < 0:
                foundTrackStart = 0
            foundTrackEnd = currentStart + silencePadding
            if foundTrackEnd > totalDuration:
                foundTrackEnd = totalDuration - 0.1
            
            suggestedTracks.append('%s - %s' % (
                secondsToMinutes(foundTrackStart),
                secondsToMinutes(foundTrackEnd)
            ))
            previousEnd = currentEnd
            continue
    
    # append the last track
    if (currentEnd+2) < totalDuration:
        foundTrackStart = previousEnd - silencePadding
        if silenceUntilEnd == True:
            foundTrackEnd = currentStart + silencePadding
        else:
            foundTrackEnd = totalDuration

        
        if foundTrackStart < 0:
            foundTrackStart = 0
        if foundTrackEnd > totalDuration:
            foundTrackEnd = totalDuration - 0.1
        suggestedTracks.append('%s - %s' % (
            secondsToMinutes(foundTrackStart),
            secondsToMinutes(foundTrackEnd)
        ))
    return suggestedTracks



''' parse the result and format it to trackStart - trackEnd\n'''
def silenceDetectResultToSilenceBoundries(resultLines, silencePadding = 1):

    foundSilences = []
    splittedSilence = resultLines.split('\n')
    for line in splittedSilence:
        if line.find('silencedetect') < 0:
            continue

        lineArgs = line.strip().split()

        # TODO: unexplainable list modification with some stdout stuff which should be skipped by condition above
        # sometimes we need to remove the first few list items to can relay on the indices
        for idx,arg in enumerate(lineArgs):
            if arg == '[silencedetect':
                lineArgs = lineArgs[idx:]
                break

        if line.find('silence_start') >= 0:
            currentStart = float(lineArgs[4])
            continue

        if line.find('silence_end') >= 0 or line.find('silence_duration') >= 0:
            currentEnd = float(lineArgs[4])

            foundSilences.append(
                'afade=enable=\'between(t,%s,%s)\':t=out:st=%s:d=%s,volume=enable=\'between(t,%s,%s)\':volume=0,afade=enable=\'between(t,%s,%s)\':t=in:st=%s:d=%s' % (
                    # fade out substitutions
                    str(currentStart),
                    str(currentStart + silencePadding),
                    str(currentStart),
                    str(silencePadding),

                    # mute substitutions
                    str(currentStart + silencePadding),
                    str(currentEnd - silencePadding),

                    # fade in substitutions
                    str(currentEnd - silencePadding),
                    str(currentEnd),
                    str(currentEnd - silencePadding),
                    str(silencePadding)
                )
            )
            continue

    return foundSilences


'''
 replaces exotic characters with similar [A-Za-z0-9] and removes all
 other characters of a string
'''
def az09(string, preserve = '', strToLower = False):
    charGroup = [
        ["_", " "],
        ["a","à","á","â","ã","ä","å","ª","а"],
        ["A","À","Á","Â","Ã","Ä","Å","А"],
        ["b","Б","б"],
        ["c","ç","¢","©"],
        ["C","Ç"],
        ["d","д"],
        ["D","Ð","Д"],
        ["e","é","ë","ê","è","е","э"],
        ["E","È","É","Ê","Ë","€","Е","Э"],
        ["f","ф"],
        ["F","Ф"],
        ["g","г"],
        ["G","Г"],
        ["h","х"],
        ["H","Х"],
        ["i","ì","í","î","ï","и","ы"],
        ["I","Ì","Í","Î","Ï","¡","И","Ы"],
        ["k","к"],
        ["K","К"],
        ["l","л"],
        ["L","Л"],
        ["m","м"],
        ["M","М"],
        ["n","ñ","н"],
        ["N","Н"],
        ["o","ò","ó","ô","õ","ö","ø","о"],
        ["O","Ò","Ó","Ô","Õ","Ö","О"],
        ["p","п"],
        ["P","П"],
        ["r","®","р"],
        ["R","Р"],
        ["s","ß","š","с"],
        ["S","$","§","Š","С"],
        ["t","т"],
        ["T","т"],
        ["u","ù","ú","û","ü","у"],
        ["U","Ù","Ú","Û","Ü","У"],
        ["v","в"],
        ["V","В"],
        ["W","Ь"],
        ["w","ь"],
        ["x","×"],
        ["y","ÿ","ý","й","ъ"],
        ["Y","Ý","Ÿ","Й","Ъ"],
        ["z","з"],
        ["Z","З"],
        ["ae","æ"],
        ["AE","Æ"],
        ["tm","™"],
        ["(","{", "[", "<"],
        [")","}", "]", ">"],
        ["0","Ø"],
        ["2","²"],
        ["3","³"],
        ["and","&"],
        ["zh","Ж","ж"],
        ["ts","Ц","ц"],
        ["ch","Ч","ч"],
        ["sh","Ш","ш","Щ","щ"],
        ["yu","Ю","ю"],
        ["ya","Я","я"]
    ]
    for cgIndex,charGroupItem in enumerate(charGroup):
        for charIndex,char in enumerate(charGroupItem):
            # TODO "preserve" currently works only with a single char, right?
            #if charGroup[cgIndex][charIndex].find(preserve) != -1:
            #    continue

            string = string.replace(charGroup[cgIndex][charIndex], charGroup[cgIndex][0])

    string = re.sub( (r'[^a-zA-Z0-9\-._%s]' % preserve), '', string)
    if strToLower == True:
        string = string.lower()
    return string
  
