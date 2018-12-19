window.stemSessions = window.stemSessions || {};
window.stemSessions['session{session.paddedCounter}'] = window.stemSessions['session{session.paddedCounter}'] || {
    date: '{session.date}',
    title: 'Jam session #{session.counter}',
    tracks: {}
};
window.stemSessions['session{session.paddedCounter}'].tracks['{track.letter}'] = window.stemSessions['session{session.paddedCounter}'].tracks['{track.letter}'] || {
    title: '{track.title}',
    artist: '{track.artist}',
    trackLetter: '{track.letter}',
    trackNumber: '{track.number}',
    session: 'session{session.paddedCounter}',
    sessionCounter: '{session.counter}',
    genre: '{track.genre}',
    duration: {track.duration},
    byteSize: {track.byteSize},
    bpm: {track.bpm},
    splitStart: {track.splitStart},
    splitEnd: {track.splitEnd},
    dbLevelBoundries: {track.dbLevelsInputFiles},
    stems: [
{stems}
    ]
};
