import os, json
from pathlib import Path
from spotify_models import ISong, IStreamed, Song, LikedSong, Podcast

class Spotify:
    pathToStreamingHistory = ''
    pathToLikedSongs = ''

    songsStreamed:    dict[str, Song]    = {}
    podcastsStreamed: dict[str, Podcast] = {}

    songsLiked: dict[str, LikedSong] = {}
    songDuplicatesFound: dict[str, int] = {}

    def __init__(self, pathToSpotifyData):
        dirList = os.listdir(pathToSpotifyData)

        jsonFileOnTopDirectory = False
        for file in dirList:
            if file.endswith('json'):
                jsonFileOnTopDirectory = True

            if jsonFileOnTopDirectory is False and file == 'Spotify_Extended_Streaming_History':
                self.pathToStreamingHistory = os.path.join(pathToSpotifyData, 'Spotify_Extended_Streaming_History')                 
            if jsonFileOnTopDirectory is False and file == 'Spotify Extended Streaming History':
                self.pathToStreamingHistory = os.path.join(pathToSpotifyData, 'Spotify Extended Streaming History')
            
            if jsonFileOnTopDirectory is False and file == 'Spotify_Account_Data':
                self.pathToLikedSongs = os.path.join(pathToSpotifyData, file, 'YourLibrary.json')
            if jsonFileOnTopDirectory is False and file == 'Spotify Account Data':
                self.pathToLikedSongs = os.path.join(pathToSpotifyData, file, 'YourLibrary.json')

            if 'Streaming_History_Audio' in file:
                jsonFileOnTopDirectory = True
                self.pathToStreamingHistory = pathToSpotifyData
            if file == 'YourLibrary.json':
                jsonFileOnTopDirectory = True
                self.pathToLikedSongs = os.path.join(pathToSpotifyData, 'YourLibrary.json')

        if self.pathToStreamingHistory is not None:
            self.parseStreamingHistory()
        if self.pathToLikedSongs is not None:
            self.parseLikedSongs()

    def parseStreamingHistory(self):
        for fileName in os.listdir(self.pathToStreamingHistory):
            if 'Streaming_History_Audio' in fileName:
                with open(os.path.join(self.pathToStreamingHistory, fileName), 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for record in data:
                        audio:IStreamed = None
                        audio = IStreamed.createFromJsonRecord(record)

                        targetDict = self.songsStreamed if type(audio) is Song else self.podcastsStreamed

                        fromDict = targetDict.pop(repr(audio), None)
                        audio.combine(fromDict)
                        targetDict[repr(audio)] = audio

    def parseLikedSongs(self):
        with open(self.pathToLikedSongs, 'r', encoding='utf8') as file:
            data = json.load(file)
            for record in data['tracks']:
                song = LikedSong(record['track'], record['artist'], record['album'])

                fromLiked = self.songsLiked.get(repr(song), None)
                if fromLiked is None:
                    self.songsLiked[repr(song)] = song
                else:
                    numOfDuplicates = self.songDuplicatesFound.pop(repr(song), 0)
                    self.songDuplicatesFound[repr(song)] = (numOfDuplicates + 1)
                    
    def _getSortedList(self, dictInQuestion, secondsCutoff):
        toReturnList = []
        msCutoff = secondsCutoff * 1000

        for song in dictInQuestion.values():
            if song.total_ms_played > msCutoff:
                toReturnList.append(song)

        return toReturnList.sort()

    def getSortedSongStreamingHistory(self, secondsCutoff = 600):
        return self._getSortedList(self.songsStreamed, secondsCutoff)
    
    def getSortedPodcastStreamingHistory(self, secondsCutoff = 600):
        return self._getSortedList(self.podcastsStreamed, secondsCutoff)
    
    def getLostSongCandidates(self, minsCutoff=10):
        if len(self.songsStreamed) == 0:
            raise AssertionError('Can only call Spotify.getLostSongCandidates() if Spotify has been fed the "Spotify Extended Streaming History" json data.')
        
        msCutoff = (minsCutoff * 60 * 1000)
        songsStreamedCopy = {}

        for song in self.songsStreamed.values():
            if song.total_ms_played > msCutoff:
                songsStreamedCopy[repr(song)] = song

        if len(self.songsLiked) > 0:
            for song in self.songsLiked.values():
                songsStreamedCopy.pop(repr(song), None)

        count = 0
        for song in songsStreamedCopy.values():
            count +=1

        candidateList = list(songsStreamedCopy.values())
        candidateList.sort()
        return candidateList
    
    def saveLostSongCandidatesToFile(self, minsCutoff=10, toFile=r'.\lost_song_candidates.txt'):
        candidates = self.getLostSongCandidates(minsCutoff)
        Spotify.saveListToFile(candidates, toFile)
        print(f'Lost Song Candidate file created at: {os.path.abspath(toFile)}')

    def saveListToFile(theList, toFile=r'.\out.txt'):
        with open(rf'{toFile}', 'w', encoding='utf-8') as file:
            for item in theList:
                file.write(str(item))
                file.write('\n\n')

