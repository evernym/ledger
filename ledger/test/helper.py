import os

from ledger.util import STH
from ledger.ledger import Ledger


def checkLeafInclusion(verifier, leafData, leafIndex, proof, treeHead):
    assert verifier.verify_leaf_inclusion(
        leaf=leafData,
        leaf_index=leafIndex,
        proof=proof,
        sth=STH(**treeHead))


def checkConsistency(tree, verifier):
    vectors = [(1, 2),
               (1, 3),
               (4, 5),
               (2, 3),
               (3, 8)]

    for oldsize, newsize in vectors:
        proof = tree.consistency_proof(oldsize, newsize)
        oldroot = tree.merkle_tree_hash(0, oldsize)
        newroot = tree.merkle_tree_hash(0, newsize)

        assert verifier.verify_tree_consistency(old_tree_size=oldsize,
                                                new_tree_size=newsize,
                                                old_root=oldroot,
                                                new_root=newroot,
                                                proof=proof)


class NoTransactionRecoveryLedger(Ledger):
    def recoverTreeFromTxnLog(self):
        pass

