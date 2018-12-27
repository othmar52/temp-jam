 

window.splitConf = {
    counter: '{session.counter}',
    date: '{session.date}',
    day: '{session.day}',
    month: '{session.month}',
    year: '{session.year}',
    title: 'Jam session #{session.counter}',
    mix: {
        filePath: 'full_length_mix_merged_not_normalized.wav',
        title: '{mix.title}',
        color: 'red',
        volume: 1,
        byteSize: '{mix.byteSize}',
        duration: '{mix.duration}',
        peaks: [{mix.peaks}]
    },
    tracks: []
};
