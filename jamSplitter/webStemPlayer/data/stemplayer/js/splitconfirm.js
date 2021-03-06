 

let waveformSettings = {
    waveColor: '#FF9C01',
    barWidth: 1,
    barGap: 0.2,
    mirrored: 1,
    colors: {
        orange: '#FF9C01',
        green: 'rgb(59,187,47)',
        red: '#FF5050',
        blue: '#5487F4',
        yellow: '#EFFE4B',
        pink: '#F8289E',
        cyan: '#00E5E5',
        violet: '#9932CC'
    }
}


window.currentView = 'sessionList';
window.currentSession = null;
window.currentTrack = null;
window.stemState = {};

window.resyncAfter = 30; // seconds
window.lastResync = window.performance.now();

document.addEventListener('DOMContentLoaded', async function() {
    drawFavicon();
    renderLoadingView();
    let renderFunc = '';

    $('.path__progress').style.opacity = 0;
    $('.page__loader h1').style.color = '#60d4ff';
    Array.from($$('.page__loader .path__logo')).forEach(function(element) {
      element.style.fill = '#60d4ff';
    });
    $('.msg__success').innerHTML = 'enjoy';

    setTimeout(
        function(){
            $('.page').innerHTML = '';
            renderTrackView();
        },
        200
    );

    
    

});
// only needed for volume-meter which seems to be not possible via file protocol
if(document.location.protocol !== 'file:') {
   window.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
}   


let load = (function() {
  // Function which returns a function: https://davidwalsh.name/javascript-functions
  function _load(tag) {
    return function(url, attributes) {
      // This promise will be used by Promise.all to determine success or failure
      return new Promise(function(resolve, reject) {
        let element = document.createElement(tag);
        element.src = url;
        element.async = true;
        for(let attrName in attributes) {
            element.setAttribute(attrName, attributes[attrName]);
        }

        // Important success and error for the promise
        element.onload = function() {
          resolve(url);
        };
        element.onerror = function() {
          reject(url);
        };

        // Inject into document to kick off loading
        document['body'].appendChild(element);
      });
    };
  }
  
  return {
    js: _load('script')
  }
})();



/**
 * 
 */
function prefixAudioPaths(sessionIndex, trackIndex, pathPrefix) {

    let stems = window.stemSessions[sessionIndex].tracks[trackIndex].stems;
    stems.forEach(function(stem, stemIndex) {
        if( typeof window.stemSessions[sessionIndex].tracks[trackIndex].stems[stemIndex].pathCorrectionDone !== 'undefined') {
            // path correction already applied (maybe caused by duplicates during testing)
            return;
        }
        window.stemSessions[sessionIndex].tracks[trackIndex].stems[stemIndex].filePath = pathPrefix + stem.filePath;
        window.stemSessions[sessionIndex].tracks[trackIndex].stems[stemIndex].pathCorrectionDone = true;
    });
}



/**
 * TODO: remove items when there is no audio avalilable
 */
async function checkConfigPaths() {
    let totalItemsToCheck = window.tracklist.length;
    let itemsChecked = 0;
    let strokeDasharray = $('.path__progress').getAttribute('stroke-dasharray');
    for(let i=0; i< window.tracklist.length; i++) {
        let sessIdx = window.tracklist[i].sessionIndex;
        for(let ii=0; ii< window.tracklist[i].tracks.length; ii++) {
            let trackIdx = window.tracklist[i].tracks[ii].trackIndex;
            let pathChunks = [
                'data', ""
            ];
            if(window.hostLevel === 'sessionlist' || window.hostLevel === 'tracklist') {
                pathChunks.unshift(window.tracklist[i].tracks[ii].trackDir);
                pathChunks.unshift('data');
            }
            if(window.hostLevel === 'sessionlist') {
                pathChunks.unshift( window.tracklist[i].sessionDir);
                pathChunks.unshift('data');
            }
            let trackDataPath = pathChunks.join("/");
            let scriptId = 'cnf-' + sessIdx.replace(/[\W_]+/g,"_") + '-' + trackIdx;
            let attributes = {
                id: scriptId,
                type: 'text/javascript',
                src: trackDataPath + 'config.js'
            };
            
            await Promise.all([load.js(trackDataPath, attributes)])
            .then(function(){
                //console.log("SUCCESS in Promise checkConfigPaths()", sessIdx, trackIdx);
                prefixAudioPaths(sessIdx, trackIdx, trackDataPath);
                return;
            })
            .catch(function(){
                //console.log("FAIL in Promise checkConfigPaths()", sessIdx, trackIdx, scriptId);
                // remove script container
                $('#' + scriptId).remove();
            });
            
        }
        itemsChecked++;
        $('.path__progress').setAttribute('stroke-dashoffset', strokeDasharray - strokeDasharray*itemsChecked / (totalItemsToCheck/100)*0.01 );
    }
    
    return true;
}

function renderLoadingView() {
    let loaderMarkup = $('#loader-markup').innerHTML;
    realDomInjection(loaderMarkup, '.page');
}

async function checkConfig() {
    
    await checkConfigPaths();

    //console.log('no more tries to load script...');
    if(!window.stemSessions) {
        console.log("config error");
        return false;
    }
    // directly select session as we have no other sessions to choose from
    if(Object.size(window.stemSessions) === 1) {
        window.currentView = 'trackList';
        window.currentSession = Object.keys(window.stemSessions)[0];
    }
    
    if(window.currentSession === null && window.currentView === 'trackList') {
        console.log("config error");
        return false;
    }
    if(!window.currentSession) {
        window.currentView = 'sessionList';
    }
    // directly render single track as we have no other content to choose from 
    if(window.currentSession && Object.size(window.stemSessions[window.currentSession].tracks) === 1) {
        window.currentView = 'singleTrack';
        window.currentTrack = Object.keys(window.stemSessions[window.currentSession].tracks)[0];
    }
}


/* genreal helper functions */
function $(elem) {
    return document.querySelector(elem);
}

function $$(elem) {
    return document.querySelectorAll(elem);
}

Object.size = function(obj) {
    let size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
};

function realDomInjection(markup, targetSelector, position='inside') {
    // assigning markupString cause errors in drawWaveform()
    // so lets create a DOM element before assigning :/
    //console.log(markup);
    var dummyWrapper = document.createElement('div');
    dummyWrapper.innerHTML = markup;
    if(position == 'after') {
        while (dummyWrapper.childNodes.length > 0) {
            $(targetSelector).parentNode.insertBefore(dummyWrapper.childNodes[(dummyWrapper.childNodes.length)-1], $(targetSelector).nextSibling);
        }
        return;
    }
    while (dummyWrapper.childNodes.length > 0) {
        $(targetSelector).appendChild(dummyWrapper.childNodes[0]);
    }
}


function getStemTitlesMarkup(stemTitles) {
    const stemTitleTemplate = $('#stemTitles-markup').innerHTML;
    let stemTitleMarkup = '';
    for(let stemTitle in stemTitles) {
        stemTitleMarkup += stemTitleTemplate
            .replace(/{stem.title}/g, stemTitle)
            .replace(/{stem.color}/g, stemTitles[stemTitle]);
    }
    return stemTitleMarkup;
}

function substituteTrackProperties(markup, track) {
    return markup
        .replace(/{track.index}/g, track.trackNumber)
        .replace(/{track.trackNumber}/g, track.trackNumber)
        .replace(/{track.trackLetter}/g, track.trackLetter)
        .replace(/{track.title}/g, track.title)
        .replace(/{track.duration}/g, formatTime(track.duration))
        .replace(/{track.bpm}/g, ((track.bpm > 0) ? '<span class="bpm">'+track.bpm+' BPM</span>' : '') )
        .replace(/{track.stemTitles}/g, getStemTitlesMarkup(track.stemTitles));
}

function substituteSessionProperties(markup, session) {
    return markup
        .replace(/{session.title}/g, session.title)
        .replace(/{session.index}/g, session.index)
        .replace(/{session.counter}/g, session.counter)
        .replace(/{session.trackCount}/g, Object.size(session.tracks))
        .replace(/{session.duration}/g, secondsToMinutes(session.duration))
        .replace(/{session.stemTitles}/g, getStemTitlesMarkup(session.stemTitles))
        .replace(/{session.date}/g, session.date)
        .replace(/{session.day}/g, session.day)
        .replace(/{session.month}/g, session.month)
        .replace(/{session.year}/g, session.year);
}

function removeAllEventListeners() {
    let body = $('body'),
    bodyClone = body.cloneNode(true);
    body.parentNode.replaceChild(bodyClone,body);
}

function getValuesChunk(values, fromPercent, toPercent) {
    
    const beginWith = values.length * fromPercent * 0.01;
    const endWith = values.length * toPercent * 0.01;
    let reduced = [];
    values.forEach(function(value, idx){
        if(idx < beginWith || idx > endWith) {
            return;
        }
        reduced.push(value);
    });
    return reduced;
}

/* render functions for different views */
function renderTrackView(autoplay) {
    $('body').classList.remove('sessionlistView');
    $('body').classList.remove('tracklistView');
    $('body').classList.add('trackView');
    removeAllEventListeners();
    $('.page').innerHTML = '';
    window.stemState = {};
    let trackviewTemplate = $('#track-markup').innerHTML;
    let stemWrapperTemplate = $('#stemTrack-markup').innerHTML;

    // create a single audio elements
    
    let lines = 3;
    let lineDuration = window.splitConf.mix.duration / lines;

    
    let stemtracksTemplate = '';
    
    for(let idx = 0; idx < lines; idx ++) {


        // substitute template markers
        let stemWrapperMarkup = stemWrapperTemplate;
        stemWrapperMarkup = stemWrapperMarkup
            .replace(/{index}/g, idx)
            .replace(/{fromSecond}/g, idx * lineDuration)
            .replace(/{toSecond}/g, (idx + 1) * lineDuration);

        stemtracksTemplate += stemWrapperMarkup;
        
    };

    //document.title = track.trackNumber + '-' + track.title + ', ' + window.stemSessions[window.currentSession].title;
    //trackviewTemplate = substituteSessionProperties(trackviewTemplate, window.stemSessions[window.currentSession])
     //   ;
    trackviewTemplate = trackviewTemplate
        //.replace(/{mainNav}/g, $('#main-nav-markup').innerHTML)
        //.replace(/{trackNavigation}/g, trackNavigationMarkup)
        //.replace(/{trackNumber}/g, track.trackNumber)
        //.replace(/{track.title}/g, track.title)
        //.replace(/{track.bpm}/g, track.bpm)
        .replace(/{stemTracks}/g, stemtracksTemplate);
    //console.log(trackviewTemplate);
    realDomInjection(trackviewTemplate, '.page');
    for(let idx = 0; idx < lines; idx ++) {

        // draw waveform
        if(window.splitConf.mix.peaks) {
            drawWaveform(
                $('#waveform__wrapper'+idx),
                getValuesChunk(window.splitConf.mix.peaks, idx*(100/lines), (idx+1)*(100/lines)),
                waveformSettings.colors[window.splitConf.mix.color]
            );
        }
        

    };
    // attach event listeners for view
    let player = $('#player0');
    
    player.addEventListener('timeupdate', function() {
        if($('.seek__progress') === null) {
            return;
        }

        $('#time__elapsed').innerHTML = formatTime(player.currentTime);
        Array.from($$('.seek__progress')).forEach(function(element) {
            if(player.currentTime > element.dataset.tosecond) {
              element.style.width = '100%';
              return;
            }
            if(player.currentTime < element.dataset.fromsecond) {
              element.style.width = '0';
              return;
            }
            let diff = player.currentTime % lineDuration;
            element.style.width = (diff)/lineDuration*100+'%';

        });
    });
    player.addEventListener('durationchange', function() {
        $('#time__total').innerHTML = formatTime(player.duration);
    });

    $('.track__play').addEventListener(
        'click', togglePlayPause, false
    );

    Array.from($$('.seek__clickarea')).forEach(function(element) {
        element.addEventListener(
            'click',
            function(e) {
                let rect = e.target.getBoundingClientRect();
                let x = e.clientX - rect.left; //x position within the element.
                let w = e.target.offsetWidth;
                let percent = x/(w/100);
                let diff = parseFloat(e.target.dataset.tosecond) - parseFloat(e.target.dataset.fromsecond);
                let targetSecond = parseFloat(e.target.dataset.fromsecond) + (percent*diff*0.01);
                $('#player0').currentTime = targetSecond;
                console.log(percent, targetSecond);

            },
            false
        );
    });

    Array.from($$('.tool__action--volume')).forEach(function(element) {
      // TODO: how to blur this elemnt to not show focus borders?
      element.addEventListener('input', setVolume);
    });


    Array.from($$('.seek__progress')).forEach(function(element) {
      element.style.width = 0;
    });
    
    if(autoplay === true) {
        $('.track__play').click();
    }

}



// redraw waveforms on resize
function redrawWaveforms() {
    try {
        window.stemSessions[window.currentSession].tracks[window.currentTrack].stems.forEach(function(stem, idx) {
            // draw waveform
            if(stem.peaks) {
                drawWaveform(
                    $('#waveform__wrapper'+idx),
                    stem.peaks,
                    waveformSettings.colors[stem.color]
                );
            }
        });
    } catch(e) {}
}

window.addEventListener("resize", debounceResizeEvent(function() {
  redrawWaveforms();
}), false);
function debounceResizeEvent(c, t) {
  onresize = function() {
    clearTimeout(t);
    t = setTimeout(c, 100);
  }
  return onresize;
}


function togglePlayPause(e) {
    e.preventDefault();
    e.currentTarget.blur();
    
    
    
    let player = $('#player0');
    let playerCmd = 'pause';
    let iconPathId = '#play-icon';
    if(player.paused) {
        playerCmd = 'play';
        iconPathId = '#pause-icon';
     }
    $('.track__play use').setAttribute( 'xlink:href', iconPathId);
    player.volume = 0.1;
    player[playerCmd]();
}

    
    
   


function setVolume(e) {
    
    e.currentTarget.blur();
    
    let playerId = e.currentTarget.dataset.target;
    $('#'+playerId).volume = e.currentTarget.value;
    
}




/* functions for drawing waveform */

function drawWaveform(targetElement, peakData, color) {
    targetElement.innerHTML = '';
    waveformSettings.canvas = document.createElement('canvas'),
    waveformSettings.context = waveformSettings.canvas.getContext('2d');
    waveformSettings.canvas.width = targetElement.offsetWidth;
    waveformSettings.canvas.height = targetElement.offsetHeight;
    waveformSettings.waveColor = color;

    let len = Math.floor(peakData.length / waveformSettings.canvas.width);
    let maxVal = getMaxVal(peakData);
    if(maxVal === 0) {
        // draw at least a one pixel line for 100% silence files
        maxVal = 1;
    }
    for (let j = 0; j < waveformSettings.canvas.width; j += waveformSettings.barWidth) {
        drawBar(
            j,
            (bufferMeasure(Math.floor(j * (peakData.length / waveformSettings.canvas.width)), len, peakData) * maxVal/10)
            *
            (waveformSettings.canvas.height / maxVal)
            +
            1
        );
    }
    targetElement.appendChild(waveformSettings.canvas);

}

function getMaxVal(inputArray) {
    let max = 0;
    for(let i=0; i<inputArray.length; i++) {
        max = (inputArray[i] > max) ? inputArray[i] : max;
    }
    return max;
}

function bufferMeasure(position, length, data) {
    let sum = 0.0;
    for (let i = position; i <= (position + length) - 1; i++) {
        sum += Math.pow(data[i], 2);
    }
    return Math.sqrt(sum / data.length);
}

function drawBar(i, h) {
    waveformSettings.context.fillStyle = waveformSettings.waveColor;
    let w = waveformSettings.barWidth;
    if (waveformSettings.barGap !== 0) {
        w *= Math.abs(1 - waveformSettings.barGap);
    }
    let x = i + (w / 2);
    let y = waveformSettings.canvas.height - h;

    if(waveformSettings.mirrored === 1) {
        y /=2;
    }
    waveformSettings.context.fillRect(x, y, w, h);
}
function formatTime(seconds) {
    if(typeof seconds === "undefined") {
        return "-- : --";
    }
    seconds     = Math.round(seconds);
    let hour    = Math.floor(seconds / 3600);
    let minutes = Math.floor(seconds / 60) % 60;
    seconds     = seconds % 60;

    if (hour > 0) {
        return hour + ":" + zeroPad(minutes, 2) + ":" + zeroPad(seconds, 2);
    }
    return zeroPad(minutes, 2) + ":" + zeroPad(seconds, 2);
}

function secondsToMinutes(seconds) {
    if(typeof seconds === "undefined") {
        return "0";
    }
    return Math.floor(seconds / 60);
}

function secondsToHours(seconds) {
    if(typeof seconds === "undefined") {
        return "0";
    }
    return Math.floor(seconds / 3600 );
}

function zeroPad(number, n) {
    let zeroPad = "" + number;
    while(zeroPad.length < n) {
        zeroPad = "0" + zeroPad;
    }
    return zeroPad;
}





function drawFavicon() {
  var canvas = document.createElement('canvas');
  var context = canvas.getContext('2d');
  var width = 64;
  var height = 64;
  var centerX = width / 2;
  var centerY = height / 2;
  canvas.setAttribute("width", width+'px');
  canvas.setAttribute("height", height+'px');

    // background
    context.fillStyle = '#000000';
    context.fillRect(0,0,width,height);
    
    let xFrom = width*0.1;
    let xTo = width * 0.9;
    
    context.beginPath();
    context.strokeStyle = waveformSettings.colors.red;
    context.lineWidth = width / 8;
    context.moveTo(xFrom, height*0.2);
    context.lineTo(xTo, height*0.2);
    context.stroke();
    
    context.beginPath();
    context.strokeStyle = waveformSettings.colors.yellow;
    context.moveTo(xFrom, height*0.4);
    context.lineTo(xTo, height*0.4);
    context.stroke();
    
    context.beginPath();
    context.strokeStyle = waveformSettings.colors.cyan;
    context.moveTo(xFrom, height*0.6);
    context.lineTo(xTo, height*0.6);
    context.stroke();
    
    context.beginPath();
    context.strokeStyle = waveformSettings.colors.violet;
    context.moveTo(xFrom, height*0.8);
    context.lineTo(xTo, height*0.8);
    context.stroke();

    // send it to the favicon!
    canvasToFavicon(canvas);

    //$('body').appendChild(canvas);
}




/* https://raw.githubusercontent.com/EvanHahn/canvas-to-favicon/master/canvas-to-favicon.js */
/* global document, navigator */

(function() {

  var canvasToFavicon;
  var supportsCanvas = !!document.createElement('canvas').getContext;

  if (supportsCanvas) {

    var head = document.head;

    var createIconElement = function() {
      var link = document.createElement('link');
      link.rel = 'icon';
      link.type = 'image/png';
      return link;
    };

    var isFirefox = !!navigator.userAgent.match(/firefox/i);

    var iconElement;

    canvasToFavicon = function(canvas) {

      if (!iconElement) {

        var existingIcons = document.querySelectorAll('link[rel="icon"]');
        for (var i = 0, len = existingIcons.length; i < len; i ++) {
          head.removeChild(existingIcons[i]);
        }

        iconElement = createIconElement();
        head.appendChild(iconElement);

      }

      // firefox needs to swap out the old element
      if (isFirefox) {
        var newEl = createIconElement();
        head.replaceChild(newEl, iconElement);
        iconElement = newEl;
      }

      iconElement.href = canvas.toDataURL('image/png');

    };

  } else {

    // noop without support
    canvasToFavicon = function() {};

  }

  if (typeof module !== 'undefined')
    module.exports = canvasToFavicon;
  else
    this.canvasToFavicon = canvasToFavicon;

})();
