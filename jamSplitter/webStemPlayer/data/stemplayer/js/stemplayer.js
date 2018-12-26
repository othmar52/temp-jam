
/**
 * STEMPLAYER EXPERIMENT
 * play multi track audios via file:/// or http[s]:// protocol
 *
 * TODO
 * welcome screen
 *      timeinterval to start with first track
 * 
 *      single session
 *          with tracklist of all availabls stems of jamsession
 * 
 *      all sessions
 *          
 *  
 *  diagramme für musizierzeit
 *      per session
 *      per alle sessions
 * 
 * welcome screen for single session html opening (not the logo screen thingy)
 * invisible seek click area to include the horizontal stem gaps for seeking
 * on resize (decrease viewport width) the stemplayer position is shit
 * audio preloader for online version (as stem sum avarage size ist 80MB per track)
 * mousemove events with pressed mousebutton on seekbar?
 * seekZero area with more tolerance than actual pixel
 * error page in case we have missing configuration
 * add some kind of search (tracknames, musicians,...)
 * any kind of visualization of actual volume values per stem during vol change  (title attribute?)
 * implement bpm tapper for manual bpm suggestion
 * 
 * play() is called too early: https://developers.google.com/web/updates/2017/06/play-request-was-interrupted
 * remember changed volume levels per session (local storage?)
 * 
 * separate html file just for detecting mix spit points???
 * unify classnames/id's (tool__action--mute, volClickArea, seekprogress)
 * improve intervaled sync between all audio stem tracks (example every 5 seconds)
 * rename volProgress to volLevel as there is no progress
 * play random track on track end
 * 
 * include suggestion for installing tiny http server with howto -> research
 * 
 * sass --watch style.scss style.css
 * 
 * NICE2HAVE
 *      pegel / mute zustände für einzeltrack über button speichern -> global für alle user
 *      stern rating system auf trackebene (session erbt nach oben)
 *          rating ergebnis 
 *      kommentieren eines tracks oder einer einzelspur
 * 
 * NAME
 *  JAM
 *      youjam
 *      jamplayer
 *      jammer
 *      stem sessions
 *      jam sessions
 *      stem jam
 *      jam2stem
 *      Rehearsal
 * 
 * https://github.com/GoogleChromeLabs/simplehttp2server
 * 
 * implement bpm tapper. @see http://www.beatsperminuteonline.com/
 * 
 */
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

/**
 * when served over http we need subdomains for audio
 * because browser refuses to load more than 4 audio resources from same origin simultaneously
 * ensure that the CORS headers on serving origins are set correctly
 *   Header set Access-Control-Allow-Origin "*"
 *   Header set Access-Control-Allow-Methods: "GET"
 * 
 * TODO: use HTTP2 
 *
 */
let httpSettings = {
    enable: true,
    audioPathSubstitutions: [
        'http://stem1.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem2.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem3.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem4.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem5.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem6.stromwerk.playground/MUSIC/stromwerk/%s',
        'http://stem7.stromwerk.playground/MUSIC/stromwerk/%s'
    ]
}

window.currentView = 'sessionList';
window.currentSession = null;
window.currentTrack = null;
window.stemState = {};

window.resyncAfter = 30; // seconds
window.lastResync = window.performance.now();

document.addEventListener('DOMContentLoaded', async function() {
    drawFavicon();
    let renderFunc = '';
    if (await checkConfig() === false) {
        // TODO: add fancy error page
        $('body').innerHTML = 'config error';
        return;
    }
    if(window.currentView === 'singleTrack') {
        renderFunc = 'renderTrackView';
    }
    if(window.currentView === 'trackList') {
        renderFunc = 'renderTracklist';
    }
    if(window.currentView === 'sessionList') {
        renderFunc = 'renderSessionlist';
    }
    if(renderFunc === '') {
        console.log('ERROR: invalid view');
    }
    setTimeout(
        function(){
            $('.page').innerHTML = '';
            window[renderFunc]();
        },
        2000
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

function substituteAudioPathsWithHttpUrls(sessionIndex, trackIndex) {
    if(document.location.protocol === 'file:') {
        return false;
    }
    if(httpSettings.enable !== true) {
        return false;
    }
    if(httpSettings.audioPathSubstitutions.length < 1) {
        return false;
    }
    let stems = window.stemSessions[sessionIndex].tracks[trackIndex].stems;
    let availableSubstitutions = httpSettings.audioPathSubstitutions.length;
    let currentSubstitution = 0
    stems.forEach(function(stem, stemIndex) {

        let httpAudioPath = httpSettings.audioPathSubstitutions[currentSubstitution];
        window.stemSessions[sessionIndex].tracks[trackIndex].stems[stemIndex].filePath = httpAudioPath.replace('%s', window.stemSessions[sessionIndex].tracks[trackIndex].stems[stemIndex].filePath );
        currentSubstitution++;
        if(currentSubstitution === availableSubstitutions) {
            currentSubstitution = 0;
        }
    });
    return true;
}


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
    substituteAudioPathsWithHttpUrls(sessionIndex, trackIndex);
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
    renderLoadingView();
    
    await checkConfigPaths();
    
    $('.path__progress').style.opacity = 0;
    $('.page__loader h1').style.color = '#60d4ff';
    Array.from($$('.page__loader .path__logo')).forEach(function(element) {
      element.style.fill = '#60d4ff';
    });

    //console.log('no more tries to load script...');
    if(!window.stemSessions) {
        console.log("config error");
        return false;
    }
    // in case sessions or tracks had been deleted in filesystem...
    calculateDurations()
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

function calculateDurations() {
    window.allSessions = {
      count: 0,
      trackCount: 0,
      duration: 0 
      
    };
    for(let sessionIdx in window.stemSessions) {
        let sessionDuration = 0;
        let stemTitlesSession = {};
        for(let trackIdx in window.stemSessions[sessionIdx].tracks) {
            sessionDuration += window.stemSessions[sessionIdx].tracks[trackIdx].duration;
            window.allSessions.trackCount++;
            let stemTitlesTrack = {};
            for(let stemIdx in window.stemSessions[sessionIdx].tracks[trackIdx].stems) {
                const stemTitle = window.stemSessions[sessionIdx].tracks[trackIdx].stems[stemIdx].title;
                const stemColor = window.stemSessions[sessionIdx].tracks[trackIdx].stems[stemIdx].color;
                stemTitlesTrack[stemTitle] = stemColor;
                stemTitlesSession[stemTitle] = stemColor;
            }
            window.stemSessions[sessionIdx].tracks[trackIdx].stemTitles =  stemTitlesTrack;
        }
        window.stemSessions[sessionIdx].duration = sessionDuration;
        window.stemSessions[sessionIdx].stemTitles = stemTitlesSession;
        
        window.allSessions.count ++;
        window.allSessions.duration += sessionDuration;
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

function renderSessionlist() {
    $('body').classList.add('sessionlistView');
    $('body').classList.remove('tracklistView');
    $('body').classList.remove('trackView');

    let sessionlistTemplate = $('#sessionList-markup').innerHTML;
    let sessionlistItemTemplate = $('#sessionListItem-markup').innerHTML;
    let sessionlistItemsMarkup = $('#sessionListTableHeader-markup').innerHTML;
    for(idx in window.stemSessions) {
        let session = window.stemSessions[idx];
        // substitute template markers for single items
        let sessionlistItemMarkup = substituteSessionProperties(sessionlistItemTemplate, session);
        sessionlistItemsMarkup += sessionlistItemMarkup;
    };
    
    sessionlistItemsMarkup = '<table class="session__list">' + sessionlistItemsMarkup + '</table>';
    // substitute template markers
    sessionlistTemplate = sessionlistTemplate.replace(/{sessionlistItems}/g, sessionlistItemsMarkup)
        .replace(/{sessions.count}/g, window.allSessions.count)
        .replace(/{sessions.trackCount}/g, window.allSessions.trackCount)
        .replace(/{sessions.duration}/g, secondsToHours(window.allSessions.duration))
        .replace(/{mainNav}/g, $('#main-nav-markup').innerHTML);
        
        
        
    realDomInjection(sessionlistTemplate, '.page');

    // add event listeners for tracklist
    Array.from($$('.navigate')).forEach(function(element) {
      element.addEventListener('click', navigate);
    });
}

function renderTracklist() {
    $('body').classList.remove('sessionlistView');
    $('body').classList.add('tracklistView');
    $('body').classList.remove('trackView');
    removeAllEventListeners();
    $('.page').innerHTML = '';

    let tracklistTemplate = $('#trackList-markup').innerHTML;
    let tracklistItemTemplate = $('#trackListItem-markup').innerHTML;
    //let tracklistItemsMarkup = '';
    let tracklistItemsMarkup = $('#trackListTableHeader-markup').innerHTML;
    for(idx in window.stemSessions[window.currentSession].tracks) {
        let track = window.stemSessions[window.currentSession].tracks[idx];
        // substitute template markers for single items
        let tracklistItemMarkup = substituteTrackProperties(tracklistItemTemplate, track)
            .replace(/{session.index}/g, window.currentSession);
        
        tracklistItemsMarkup += tracklistItemMarkup;
    };
    // too bad .innerHTML does not allow invalid markup
    // so we have to place wrapping table markup here and not withen the <template> container ...
    //tracklistItemsMarkup = '<table class="track__list"><thead>' + $('#trackListTableHeader-markup').innerHTML + '</thead><tbody>' + tracklistItemsMarkup + '</tbody></table>';
    tracklistItemsMarkup = '<table class="track__list"><tbody>' + tracklistItemsMarkup + '</tbody></table>';
    
    // substitute template markers
    //console.log(tracklistTemplate);
    tracklistTemplate = substituteSessionProperties(tracklistTemplate, window.stemSessions[window.currentSession])
        .replace(/{albumTitle}/g, window.stemSessions[window.currentSession].title)
        .replace(/{mainNav}/g, $('#main-nav-markup').innerHTML)
        .replace(/{tracklistItems}/g, tracklistItemsMarkup);
    realDomInjection(tracklistTemplate, '.page');

    // add event listeners for tracklist view
    Array.from($$('.navigate')).forEach(function(element) {
      element.addEventListener('click', navigate);
    });
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

    // create all audio elements
    let stemtracksTemplate = '';
    window.stemSessions[window.currentSession].tracks[window.currentTrack].stems.forEach(function(stem, idx) {
        window.stemState['player'+idx] = {
            isMuted: false,
            isSoloed: false,
            isIsolated: false,
            volLevel: stem.volume
        };

        // substitute template markers
        let stemWrapperMarkup = stemWrapperTemplate;
        stemWrapperMarkup = stemWrapperMarkup
            .replace(/{index}/g, idx)
            .replace(/{audiosource}/g, stem.filePath)
            .replace(/{color}/g, stem.color)
            .replace(/{title}/g, stem.title);

        stemtracksTemplate += stemWrapperMarkup;
        
    });
    let trackNavItemTemplate = $('#trackBulletNavigation-markup').innerHTML;
    let trackNavigationMarkup = ''
    for(let trackIdx in window.window.stemSessions[window.currentSession].tracks) {
        let trackNavItemMarkup = trackNavItemTemplate;
        let track = window.stemSessions[window.currentSession].tracks[trackIdx];
        trackNavItemMarkup = substituteTrackProperties(trackNavItemMarkup, track)
            .replace(/{session.index}/g, window.currentSession)
            .replace(/{session.title}/g, window.stemSessions[window.currentSession].title)
            .replace(/{active}/g, ((window.currentTrack === trackIdx ) ? 'active': ''));
        trackNavigationMarkup += trackNavItemMarkup;
    }
    let track = window.stemSessions[window.currentSession].tracks[window.currentTrack];
    document.title = track.trackNumber + '-' + track.title + ', ' + window.stemSessions[window.currentSession].title;
    trackviewTemplate = substituteSessionProperties(trackviewTemplate, window.stemSessions[window.currentSession])
        .replace(/{mainNav}/g, $('#main-nav-markup').innerHTML)

        
        .replace(/{trackNavigation}/g, trackNavigationMarkup)
        .replace(/{trackNumber}/g, track.trackNumber)
        .replace(/{track.title}/g, track.title)
        .replace(/{track.bpm}/g, track.bpm)
        .replace(/{stemTracks}/g, stemtracksTemplate);
    //console.log(trackviewTemplate);
    realDomInjection(trackviewTemplate, '.page');
    window.stemSessions[window.currentSession].tracks[window.currentTrack].stems.forEach(function(stem, idx) {
        // set width of volume slider
        $('#tool__action--volume'+idx).value = stem.volume;

        // draw waveform
        if(stem.peaks) {
            drawWaveform(
                $('#waveform__wrapper'+idx),
                stem.peaks,
                waveformSettings.colors[stem.color]
            );
        }
        // createMediaElementSource() does not work for file:/// protocol
        if(document.location.protocol === 'file:') {
            return
        }

        // create volume meter
        let audioElement = $('#player'+idx);
        let meterElement = document.createElement('div');
        meterElement.setAttribute('id', 'dbmeter'+idx);
        meterElement.setAttribute('class', 'dbmeter');
        $('#line_meta'+idx).insertBefore(meterElement, $('#line_meta'+idx).firstChild);
        let webAudioPeakMeter = new WebAudioPeakMeter();
        audioElement.crossOrigin = 'anonymous';
        let sourceNode = window.audioCtx.createMediaElementSource(audioElement);
        sourceNode.connect(window.audioCtx.destination);
        let meterNode = webAudioPeakMeter.createMeterNode(sourceNode, window.audioCtx);
        webAudioPeakMeter.createMeter(meterElement, meterNode, {});
        

    });
    // attach event listeners for view
    let player = $('#player0');
    
    player.addEventListener('timeupdate', function() {
        if($('.seek__progress') === null) {
            return;
        }
        // resynchronize all stem tracks every 5 seconds
        // TODO: is it better to attach an isPlaying listener and use setInterval instead???
        //if(0.0001 < (player.currentTime % 5)  < 0.1) {
        if(player.currentTime % window.resyncAfter < 0.1 && player.currentTime % window.resyncAfter  > 0) {
            resyncStems();
        }
        $('#time__elapsed').innerHTML = formatTime(player.currentTime);
        Array.from($$('.seek__progress')).forEach(function(element) {
            element.style.width = (player.currentTime +.25)/player.duration*100+'%';
        });
    });
    player.addEventListener('durationchange', function() {
        $('#time__total').innerHTML = formatTime(player.duration);
    });
    player.addEventListener('ended', handleTrackEnded, false);

    $('.track__play').addEventListener(
        'click', togglePlayPause, false
    );

    $('.tool__action--mute').addEventListener(
        'click', unmuteAllStems, false
    );

    $('.tool__action--solo').addEventListener(
        'click', unsoloAllStems, false
    );
    Array.from($$('.seek__clickarea')).forEach(function(element) {
        element.addEventListener(
            'click',
            function(e) {
                let rect = e.target.getBoundingClientRect();
                let x = e.clientX - rect.left; //x position within the element.
                let w = e.target.offsetWidth;
                let percent = x/(w/100);
                seekPercent(percent);
            },
            false
        );
    });

    Array.from($$('.tool__action--isolate')).forEach(function(element) {
      element.addEventListener('click', toggleIsolateStem);
    });

    Array.from($$('.tool__action--solo')).forEach(function(element) {
      element.addEventListener('click', toggleSoloStem);
    });

    Array.from($$('.tool__action--mute')).forEach(function(element) {
      element.addEventListener('click', toggleMuteStem);
    });

    Array.from($$('.tool__action--volume')).forEach(function(element) {
      // TODO: how to blur this elemnt to not show focus borders?
      element.addEventListener('input', setVolume);
    });

    Array.from($$('.navigate')).forEach(function(element) {
      element.addEventListener('click', navigate);
    });

    Array.from($$('.seek__progress')).forEach(function(element) {
      element.style.width = 0;
    });
    
    if(autoplay === true) {
        $('.track__play').click();
    }

}

function getNextSiblings(elem, filter) {
    var sibs = [];
    while (elem = elem.nextSibling) {
        if (elem.nodeType === 3) continue; // text node
        if (!filter || filter(elem)) sibs.push(elem);
    }
    return sibs;
}

function navigate(e) {
    e.preventDefault();
    //try {
    //    seekPercent(0);
    //    $('#seekprogress').style.width = 0;
    //} catch(e) { }
    removeAllEventListeners();
    $('.page').innerHTML = '';
    if(e.currentTarget.dataset.targettype === 'sessionlist') {
        window.currentSession = null;
        window.currentTrack = null;
        renderSessionlist();
        return;
    }
    if(e.currentTarget.dataset.targettype === 'tracklist') {
        window.currentSession = e.currentTarget.dataset.targetsession;
        window.currentTrack = null;
        renderTracklist();
        return;
    }
    if(e.currentTarget.dataset.targettype === 'track') {
        window.currentSession = e.currentTarget.dataset.targetsession;
        window.currentTrack = e.currentTarget.dataset.targettrack;
        renderTrackView(true);
        return;
    }
}

function handleTrackEnded() {
    // TODO: add random toggler
    // for now load the next track if available. otherwise stop
    seekPercent(0);
    let foundCurrentSession = false;
    let foundCurrentTrack = false;
    for(let sessionIdx in window.stemSessions) {
        if(sessionIdx !== window.currentSession && foundCurrentSession === false) {
          continue;
        }
        for(let trackIdx in window.stemSessions[sessionIdx].tracks) {
            if(sessionIdx === window.currentSession && trackIdx === window.currentTrack) {
                foundCurrentSession = true;
                foundCurrentTrack = true;
                continue;
            }
            if(foundCurrentTrack === true) {
                window.currentSession = sessionIdx;
                window.currentTrack = trackIdx;
                renderTrackView(true);
                return;
            }
        }
    }
    console.log('TODO what to do if very last track has ended?');
    $('#track__play').classList.remove('active');
}
/* functions for all stems stems */
function seekPercent(percent) {
    let targetSecond = false;
    for(idx in window.stemState) {
        let player = $('#'+idx);
        if(targetSecond === false) {
            targetSecond = player.duration * percent * 0.01;
        }
        player.currentTime = targetSecond;
    }
    window.lastResync = window.performance.now();
}
function resyncStems() {
    let deltaLastResync = window.performance.now() - window.lastResync;
    if(deltaLastResync < window.resyncAfter) {
        console.log('deltaLastResync skip');
        return;
    }
    
    let targetSecond = 0;
    for(idx in window.stemState) {
        let player = $('#'+idx);
        if(idx === 'player0') {
            targetSecond = player.currentTime;
            window.lastResync = window.performance.now();
            console.log('resync ' + targetSecond);
            continue;
        }
        player.currentTime = targetSecond;
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
    let playerCmd = null;
    let iconPathId = null;
    for(playerId in window.stemState) {
        let player = $('#' + playerId);
        if(playerCmd === null) {
            playerCmd = 'pause';
            iconPathId = '#play-icon';
            if(player.paused) {
                playerCmd = 'play';
                iconPathId = '#pause-icon';
            }
        }
        $('.track__play use').setAttribute( 'xlink:href', iconPathId);
        player[playerCmd]();
        player.volume = window.stemState[playerId].volLevel;
    }
}

function unmuteAllStems(e) {
    e.currentTarget.blur();
    for(playerId in window.stemState) {
        window.stemState[playerId].isMuted = false;
    }
    setVolumesAndButtonStates();
}

function unsoloAllStems(e) {
    e.currentTarget.blur();
    for(playerId in window.stemState) {
        window.stemState[playerId].isSoloed = false;
    }
    setVolumesAndButtonStates();
}










/* functions for isolate|solo|mute for single stems */

function toggleIsolateStem(e) {
    e.currentTarget.blur();
    let playerId = e.currentTarget.dataset.target;
    if(window.stemState[playerId].isIsolated === true) {
        unisolateStem(playerId);
        return;
    }
    isolateStem(playerId);
}

function isolateStem(playerId) {
    for(idx in window.stemState) {
        window.stemState[idx].isIsolated = false;
    }
    window.stemState[playerId].isIsolated = true;
    setVolumesAndButtonStates();
}

function unisolateStem(playerId) {
    window.stemState[playerId].isIsolated = false;
    setVolumesAndButtonStates();
}

function guiUnisolateStem(playerIdx) {
    $('#tool__action--isolate' + playerIdx).classList.remove('active');
}

function guiIsolateStem(playerIdx) {
    $('#tool__action--isolate' + playerIdx).classList.add('active');
}

function toggleSoloStem(e) {
    e.currentTarget.blur();
    let playerId = e.currentTarget.dataset.target;
    if(window.stemState[playerId].isSoloed === true) {
        unsoloStem(playerId);
        return;
    }
    soloStem(playerId);
}

function soloStem(playerId) {
    window.stemState[playerId].isSoloed = true;
    setVolumesAndButtonStates();
}

function unsoloStem(playerId) {
    window.stemState[playerId].isSoloed = false;
    setVolumesAndButtonStates();
}

function guiUnsoloStem(playerIdx) {
    $('#tool__action--solo' + playerIdx).classList.remove('active');
}

function guiSoloStem(playerIdx) {
    $('#tool__action--solo' + playerIdx).classList.add('active');
}

function toggleMuteStem(e) {
    e.currentTarget.blur();
    let playerId = e.currentTarget.dataset.target;
    if(window.stemState[playerId].isMuted === true) {
        unmuteStem(playerId);
        return;
    }
    muteStem(playerId);
}

function muteStem(playerId) {
    window.stemState[playerId].isMuted = true;
    setVolumesAndButtonStates();
}

function unmuteStem(playerId) {
    window.stemState[playerId].isMuted = false;
    setVolumesAndButtonStates();
}

function guiUnmuteStem(playerIdx) {
    $('#tool__action--mute' + playerIdx).classList.remove('active');
}

function guiMuteStem(playerIdx) {
    $('#tool__action--mute' + playerIdx).classList.add('active');
}

function muteInternal(playerIdx) {
    $('#player' + playerIdx).muted = true;
    $('#track__line' + playerIdx).classList.add('track__line--audio-muted');
}

function unmuteInternal(playerIdx) {
    $('#player' + playerIdx).muted = false;
    $('#track__line' + playerIdx).classList.remove('track__line--audio-muted');
}

function setVolumesAndButtonStates() {
    
    let anyTrackIsolated = false;
    let anyTrackSoloed = false;
    let anyTrackMuted = false;
    for(idx in window.stemState) {
        if(window.stemState[idx].isIsolated === true) {
            anyTrackIsolated = true;
        }
        if(window.stemState[idx].isSoloed === true) {
            anyTrackSoloed = true;
        }
        if(window.stemState[idx].isMuted === true) {
            anyTrackMuted = true;
        }
    } 

    // highest priority isolate
    if(anyTrackIsolated === true) {
        for(playerId in window.stemState) {
            let idx = playerId.replace( /^\D+/g, '');
            guiUnmuteStem(idx);
            guiUnsoloStem(idx);
            if(window.stemState[playerId].isIsolated === true) {
                guiIsolateStem(idx);
                unmuteInternal(idx);
                continue;
            }
            guiUnisolateStem(idx)
            muteInternal(idx);
        }
        $('.tool__action--solo').classList.remove('active');
        $('.tool__action--mute').classList.remove('active');
        return;
    }

    // 2nd priority solo
    if(anyTrackSoloed === true) {
        for(playerId in window.stemState) {
            let idx = playerId.replace( /^\D+/g, '');
            guiUnmuteStem(idx);
            guiUnisolateStem(idx);
            if(window.stemState[playerId].isSoloed === true) {
                guiSoloStem(idx);
                unmuteInternal(idx);
                continue;
            }
            guiUnsoloStem(idx)
            muteInternal(idx);
        }
        $('.tool__action--solo').classList.add('active');
        $('.tool__action--mute').classList.remove('active');
        return;
    }

    // 3rd priority mute
    let highlightUnmuteAll = false;
    for(playerId in window.stemState) {
        let idx = playerId.replace( /^\D+/g, '');
        guiUnsoloStem(idx);
        guiUnisolateStem(idx);
        if(window.stemState[playerId].isMuted === true) {
            guiMuteStem(idx);
            muteInternal(idx);
            highlightUnmuteAll = true;
            continue;
        }
        guiUnmuteStem(idx)
        unmuteInternal(idx);
        $('#player'+idx).volume = window.stemState['player'+idx].volLevel;
    }
    $('.tool__action--solo').classList.remove('active');
    $('.tool__action--mute').classList[(highlightUnmuteAll === true)?'add':'remove']('active');

}



function setVolume(e) {
    
    e.currentTarget.blur();
    
    let playerId = e.currentTarget.dataset.target;
    window.stemState[playerId].volLevel = e.currentTarget.value;
    //$('#tool__action--volume'+idx).value = stem.volume;
    $('#'+playerId).volume = window.stemState[playerId].volLevel;
    
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
