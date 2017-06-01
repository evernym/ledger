import os
import shutil
from typing import List
from ledger.stores.file_store import FileStore
from ledger.stores.text_file_store import TextFileStore


class ChunkedFileStore(FileStore):
    """
    Implements a FileStore with chunking behavior.

    Stores chunks of data into separate files. The chunking of data is
    determined by the `chunkSize` parameter. Each chunk of data is written to a
    different file.
    The naming convention of the files is such that the starting number of each
    chunk is the file name, i.e. for a chunkSize of 1000, the first file would
    be 1, the second 1001 etc.

    Every instance of ChunkedFileStore maintains its own directory for
    storing the chunked data files.
    """

    firstChunkIndex = 1

    @staticmethod
    def _fileNameToChunkIndex(fileName):
        try:
            return int(fileName)
        except:
            return None

    @staticmethod
    def _chunkIndexToFileName(index):
        return str(index)

    def __init__(self,
                 dbDir,
                 dbName,
                 isLineNoKey: bool=False,
                 storeContentHash: bool=True,
                 chunkSize: int=1000,
                 ensureDurability: bool=True,
                 chunkStoreConstructor=TextFileStore,
                 defaultFile=None):
        """
        
        :param chunkSize: number of items in one chunk. Cannot be lower then number of items in defaultFile 
        :param chunkStoreConstructor: constructor of store for single chunk
        """

        assert chunkStoreConstructor is not None

        super().__init__(dbDir,
                         dbName,
                         isLineNoKey,
                         storeContentHash,
                         ensureDurability,
                         defaultFile=defaultFile)

        self.chunkSize = chunkSize
        self.itemNum = 1  # chunk size counter
        self.dataDir = os.path.join(dbDir, dbName)  # chunk files destination
        self.currentChunk = None  # type: FileStore
        self.currentChunkIndex = None  # type: int

        self._chunkCreator = lambda name: \
            chunkStoreConstructor(self.dataDir,
                                  name,
                                  isLineNoKey,
                                  storeContentHash,
                                  ensureDurability)

        self._initDB(dbDir, dbName)

    def _prepareFiles(self, dbDir, dbName, defaultFile):

        def getFileSize(file):
            with self._chunkCreator(file) as chunk:
                return chunk.numKeys

        path = os.path.join(dbDir, dbName)
        os.mkdir(path)
        if defaultFile:
            if self.chunkSize < getFileSize(defaultFile):
                raise ValueError("Default file is larger than chunk size")
            firstChunk = os.path.join(path, str(self.firstChunkIndex))
            shutil.copy(defaultFile, firstChunk)

    def _initDB(self, dataDir, dbName) -> None:
        super()._initDB(dataDir, dbName)
        path = os.path.join(dataDir, dbName)
        if not os.path.isdir(path):
            raise ValueError("Transactions file {} is not directory"
                             .format(path))
        self._useLatestChunk()

    def _useLatestChunk(self) -> None:
        """
        Moves chunk cursor to the last chunk
        """
        self._useChunk(self._findLatestChunk())

    def _findLatestChunk(self) -> int:
        """
        Determine which chunk is the latest
        :return: index of a last chunk
        """
        chunks = self._listChunks()
        if len(chunks) > 0:
            return chunks[-1]
        return ChunkedFileStore.firstChunkIndex

    def _startNextChunk(self) -> None:
        """
        Close current and start next chunk
        """
        if self.currentChunk is None:
            self._useLatestChunk()
        else:
            self._useChunk(self.currentChunkIndex + self.chunkSize)

    def _useChunk(self, index) -> None:
        """
        Switch to specific chunk

        :param index:
        """

        if self.currentChunk is not None:
            if self.currentChunkIndex == index and \
                    not self.currentChunk.closed:
                return
            self.currentChunk.close()

        self.currentChunk = self._openChunk(index)
        self.currentChunkIndex = index
        self.itemNum = self.currentChunk.numKeys + 1

    def _openChunk(self, index) -> FileStore:
        """
        Load chunk from file

        :param index: chunk index
        :return: opened chunk
        """

        return self._chunkCreator(ChunkedFileStore._chunkIndexToFileName(index))

    def _get_key_location(self, key) -> (int, int):
        """
        Return chunk no and 1-based offset of key
        :param key:
        :return:
        """
        key = int(key)
        remainder = key % self.chunkSize
        addend = ChunkedFileStore.firstChunkIndex
        chunk_no = key - remainder + addend if remainder \
            else key - self.chunkSize + addend
        offset = remainder or self.chunkSize
        return chunk_no, offset

    def put(self, value, key=None) -> None:
        if self.itemNum > self.chunkSize:
            self._startNextChunk()
            self.itemNum = 1
        self.itemNum += 1
        self.currentChunk.put(value, key)

    def get(self, key) -> str:
        """
        Determines the file to retrieve the data from and retrieves the data.

        :return: value corresponding to specified key
        """
        # TODO: get is creating files when a key is given which is more than
        # the store size
        chunk_no, offset = self._get_key_location(key)
        with self._openChunk(chunk_no) as chunk:
            return chunk.get(str(offset))

    def reset(self) -> None:
        """
        Clear all data in file storage.
        """
        self.close()
        for f in os.listdir(self.dataDir):
            os.remove(os.path.join(self.dataDir, f))
        self._useLatestChunk()

    def _getLines(self) -> List[str]:
        """
        Lists lines in a store (all chunks)

        :return: lines
        """

        allLines = []
        chunkIndices = self._listChunks()
        for chunkIndex in chunkIndices:
            with self._openChunk(chunkIndex) as chunk:
                # implies that getLines is logically protected, not private
                allLines.extend(chunk._getLines())
        return allLines

    def open(self) -> None:
        self._useLatestChunk()

    def close(self):
        if self.currentChunk is not None:
            self.currentChunk.close()
        self.currentChunk = None
        self.currentChunkIndex = None
        self.itemNum = None

    def _listChunks(self):
        """
        Lists stored chunks

        :return: sorted list of available chunk indices
        """
        chunks = []
        for fileName in os.listdir(self.dataDir):
            index = ChunkedFileStore._fileNameToChunkIndex(fileName)
            if index is not None:
                chunks.append(index)
        return sorted(chunks)

    def iterator(self, includeKey=True, includeValue=True, prefix=None):
        """
        Store iterator

        :return: Iterator for data in all chunks
        """

        if not (includeKey or includeValue):
            raise ValueError("At least one of includeKey or includeValue "
                             "should be true")
        lines = self._getLines()
        if includeKey and includeValue:
            return self._keyValueIterator(lines, prefix=prefix)
        if includeValue:
            return self._valueIterator(lines, prefix=prefix)
        return self._keyIterator(lines, prefix=prefix)

    def get_range(self, start, end):
        assert start <= end

        if start == end:
            res = self.get(start)
            return [(start, res)] if res is not None else []

        start_chunk_no, start_offset = self._get_key_location(start)

        end_chunk_no, end_offset = self._get_key_location(end)
        if start_chunk_no == end_chunk_no:
            assert end_offset >= start_offset
            with self._openChunk(start_chunk_no) as chunk:
                lines = [(self._parse_line(j, key=str(i))) for i, j in
                         zip(range(start, end+1),
                             chunk._getLines()[start_offset-1:end_offset])]
        else:
            lines = []
            current_chunk_no = start_chunk_no
            while current_chunk_no <= end_chunk_no:
                with self._openChunk(current_chunk_no) as chunk:
                    if current_chunk_no == start_chunk_no:
                        current_chunk_lines = chunk._getLines()[start_offset - 1:]
                        lines.extend(
                            [(self._parse_line(j, key=str(i))) for i, j in
                             zip(range(start, start+len(current_chunk_lines)+1),
                                 current_chunk_lines)]
                        )
                    elif current_chunk_no == end_chunk_no:
                        current_chunk_lines = chunk._getLines()[:end_offset]
                        lines.extend(
                            [(self._parse_line(j, key=str(i))) for i, j in
                             zip(range(end-len(current_chunk_lines)+1, end+1),
                                 current_chunk_lines)]
                        )
                    else:
                        current_chunk_lines = chunk._getLines()
                        lines.extend(
                            [(self._parse_line(j, key=str(i))) for i, j in
                             zip(range(current_chunk_no,
                                       current_chunk_no + self.chunkSize + 1),
                                 current_chunk_lines)]
                        )
                current_chunk_no += self.chunkSize
        return lines

    def appendNewLineIfReq(self):
        self._useLatestChunk()
        self.currentChunk.appendNewLineIfReq()

    @property
    def numKeys(self):
        chunks = self._listChunks()
        num_chunks = len(chunks)
        if num_chunks == 0:
            return 0
        count = (num_chunks-1)*self.chunkSize
        last_chunk = self._openChunk(chunks[-1])
        count += len(last_chunk._getLines())
        last_chunk.close()
        return count

    @property
    def closed(self):
        return self.currentChunk is None
