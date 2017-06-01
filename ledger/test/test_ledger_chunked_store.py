import string
import types
from binascii import hexlify

import pytest

from ledger.compact_merkle_tree import CompactMerkleTree
from ledger.ledger import Ledger
from ledger.serializers.json_serializer import JsonSerializer
from ledger.stores.chunked_file_store import ChunkedFileStore
from ledger.stores.file_hash_store import FileHashStore
from ledger.test.test_file_hash_store import generateHashes

chunk_size = 5


@pytest.fixture(scope="function")
def ledger(tempdir):
    store = ChunkedFileStore(tempdir,
                             'transactions',
                             isLineNoKey=True,
                             chunkSize=chunk_size,
                             storeContentHash=False,
                             ensureDurability=False)
    ledger = Ledger(CompactMerkleTree(hashStore=FileHashStore(dataDir=tempdir)),
                    dataDir=tempdir, serializer=JsonSerializer(),
                    transactionLogStore=store)
    ledger.reset()
    return ledger


def test_add_txns(tempdir, ledger):
    txns = []
    hashes = [hexlify(h).decode() for h in generateHashes(60)]
    for i in range(20):
        txns.append({
            'a': hashes.pop(),
            'b': hashes.pop(),
            'c': hashes.pop()
        })

    for txn in txns:
        ledger.add(txn)

    for s, t in ledger.getAllTxn(frm=1, to=20).items():
        s = int(s)
        assert txns[s-1] == t

    for s, t in ledger.getAllTxn(frm=3, to=8).items():
        s = int(s)
        assert txns[s-1] == t

    for s, t in ledger.getAllTxn(frm=5, to=17).items():
        s = int(s)
        assert txns[s-1] == t

    for s, t in ledger.getAllTxn(frm=6, to=10).items():
        s = int(s)
        assert txns[s-1] == t