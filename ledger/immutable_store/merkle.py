import base64
import functools
import hashlib
import logging
from binascii import hexlify

from ledger.immutable_store import error
from ledger.immutable_store.merkle_tree import MerkleTree
from ledger.immutable_store.stores.hash_store import HashStore
from ledger.immutable_store.util import count_bits_set, lowest_bit_set


class TreeHasher(object):
    """Merkle hasher with domain separation for leaves and nodes."""

    def __init__(self, hashfunc=hashlib.sha256):
        self.hashfunc = hashfunc

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.hashfunc)

    def __str__(self):
        return repr(self)

    def hash_empty(self):
        hasher = self.hashfunc()
        return hasher.digest()

    def hash_leaf(self, data):
        hasher = self.hashfunc()
        hasher.update(b"\x00" + data)
        return hasher.digest()

    def hash_children(self, left, right):
        hasher = self.hashfunc()
        hasher.update(b"\x01" + left + right)
        return hasher.digest()

    def _hash_full(self, leaves, l_idx, r_idx):
        """Hash the leaves between (l_idx, r_idx) as a valid entire tree.

        Note that this is only valid for certain combinations of indexes,
        depending on where the leaves are meant to be located in a parent tree.

        Returns:
            (root_hash, hashes): where root_hash is that of the entire tree,
            and hashes are that of the full (i.e. size 2^k) subtrees that form
            the entire tree, sorted in descending order of size.
        """
        width = r_idx - l_idx
        if width < 0 or l_idx < 0 or r_idx > len(leaves):
            raise IndexError("%s,%s not a valid range over [0,%s]" % (
                l_idx, r_idx, len(leaves)))
        elif width == 0:
            return self.hash_empty(), ()
        elif width == 1:
            leaf_hash = self.hash_leaf(leaves[l_idx])
            return leaf_hash, (leaf_hash,)
        else:
            # next smallest power of 2
            split_width = 2**((width - 1).bit_length() - 1)
            assert split_width < width <= 2*split_width
            l_root, l_hashes = self._hash_full(leaves, l_idx, l_idx+split_width)
            assert len(l_hashes) == 1 # left tree always full
            r_root, r_hashes = self._hash_full(leaves, l_idx+split_width, r_idx)
            root_hash = self.hash_children(l_root, r_root)
            return (root_hash, (root_hash,) if split_width*2 == width else
                                l_hashes + r_hashes)

    def hash_full_tree(self, leaves):
        """Hash a set of leaves representing a valid full tree."""
        root_hash, hashes = self._hash_full(leaves, 0, len(leaves))
        assert len(hashes) == count_bits_set(len(leaves))
        assert (self._hash_fold(hashes) == root_hash if hashes else
                root_hash == self.hash_empty())
        return root_hash

    def _hash_fold(self, hashes):
        rev_hashes = iter(hashes[::-1])
        accum = next(rev_hashes)
        for cur in rev_hashes:
            accum = self.hash_children(cur, accum)
        return accum


class CompactMerkleTree(MerkleTree):
    """Compact representation of a Merkle Tree that permits only extension.

    Attributes:
        tree_size: Number of leaves in this tree.
        hashes: That of the full (i.e. size 2^k) subtrees that form this tree,
            sorted in descending order of size.
    """

    def __init__(self, hasher=TreeHasher(), tree_size=0, hashes=(),
                 hashStore=None):

        # These two queues should be written to two simple position-accessible
        # arrays (files, database tables, etc.)
        self.hashStore = hashStore  # type: HashStore
        self.__hasher = hasher
        self._update(tree_size, hashes)

    def _update(self, tree_size, hashes):
        bits_set = count_bits_set(tree_size)
        num_hashes = len(hashes)
        if num_hashes != bits_set:
            msgfmt = "number of hashes != bits set in tree_size: %s vs %s"
            raise ValueError(msgfmt % (num_hashes, bits_set))
        self.__tree_size = tree_size
        self.__hashes = tuple(hashes)
        # height of the smallest subtree, or 0 if none exists (empty tree)
        self.__mintree_height = lowest_bit_set(tree_size)
        self.__root_hash = None

    def load(self, other):
        """Load this tree from a dumb data object for serialisation.

        The object must have attributes tree_size:int and hashes:list.
        """
        self._update(other.tree_size, other.hashes)

    def save(self, other):
        """Save this tree into a dumb data object for serialisation.

        The object must have attributes tree_size:int and hashes:list.
        """
        other.tree_size = self.__tree_size
        other.hashes[:] = self.__hashes

    def __copy__(self):
        return self.__class__(self.__hasher, self.__tree_size, self.__hashes)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (
            self.__class__.__name__,
            self.__hasher, self.__tree_size, self.__hashes)

    def __len__(self):
        return self.__tree_size

    @property
    def tree_size(self):
        return self.__tree_size

    @property
    def hashes(self):
        return self.__hashes

    def root_hash(self):
        """Returns the root hash of this tree. (Only re-computed on change.)"""
        if self.__root_hash is None:
            self.__root_hash = (
                self.__hasher._hash_fold(self.__hashes)
                if self.__hashes else self.__hasher.hash_empty())
        return self.__root_hash

    def root_hash_hex(self):
        """Returns the root hash of this tree. (Only re-computed on change.)"""
        return hexlify(self.root_hash())

    def _push_subtree(self, leaves):
        """Extend with a full subtree <= the current minimum subtree.

        The leaves must form a full subtree, i.e. of size 2^k for some k. If
        there is a minimum subtree (i.e. __mintree_height > 0), then the input
        subtree must be smaller or of equal size to the minimum subtree.

        If the subtree is smaller (or no such minimum exists, in an empty tree),
        we can simply append its hash to self.hashes, since this maintains the
        invariant property of being sorted in descending size order.

        If the subtree is of equal size, we are in a similar situation to an
        addition carry. We handle it by combining the two subtrees into a larger
        subtree (of size 2^(k+1)), then recursively trying to add this new
        subtree back into the tree.

        Any collection of leaves larger than the minimum subtree must undergo
        additional partition to conform with the structure of a merkle tree,
        which is a more complex operation, performed by extend().
        """
        size = len(leaves)
        if count_bits_set(size) != 1:
            raise ValueError("invalid subtree with size != 2^k: %s" % size)
        # in general we want the highest bit, but here it's also the lowest bit
        # so just reuse that code instead of writing a new highest_bit_set()
        subtree_h, mintree_h = lowest_bit_set(size), self.__mintree_height
        if mintree_h > 0 and subtree_h > mintree_h:
            raise ValueError("subtree %s > current smallest subtree %s" % (
                subtree_h, mintree_h))
        root_hash, hashes = self.__hasher._hash_full(leaves, 0, size)
        assert hashes == (root_hash,)

        if self.hashStore:
            for h in hashes:
                self.hashStore.writeLeaf(h)

        new_node_hashes = self.__push_subtree_hash(subtree_h, root_hash)

        nodes = [(self.tree_size, height, h) for h, height in new_node_hashes]
        if self.hashStore:
            for node in nodes:
                self.hashStore.writeNode(node)

    def __push_subtree_hash(self, subtree_h, sub_hash):
        size, mintree_h = 1 << (subtree_h - 1), self.__mintree_height
        if subtree_h < mintree_h or mintree_h == 0:
            self._update(self.tree_size + size, self.hashes + (sub_hash,))
            return []
        else:
            assert subtree_h == mintree_h
            # addition carry - rewind the tree and re-try with bigger subtree
            prev_hash = self.hashes[-1]
            self._update(self.tree_size - size, self.hashes[:-1])
            new_mintree_h = self.__mintree_height
            assert mintree_h < new_mintree_h or new_mintree_h == 0
            next_hash = self.__hasher.hash_children(prev_hash, sub_hash)

            return [(next_hash, subtree_h)] + self.__push_subtree_hash(
                subtree_h + 1, next_hash)

    def append(self, new_leaf):
        """Append a new leaf onto the end of this tree and return the audit path"""
        auditPath = list(reversed(self.__hashes))
        self._push_subtree([new_leaf])
        return auditPath

    def extend(self, new_leaves):
        """Extend this tree with new_leaves on the end.

        The algorithm works by using _push_subtree() as a primitive, calling
        it with the maximum number of allowed leaves until we can add the
        remaining leaves as a valid entire (non-full) subtree in one go.
        """
        size = len(new_leaves)
        final_size = self.tree_size + size
        idx = 0
        while True:
            # keep pushing subtrees until mintree_size > remaining
            max_h = self.__mintree_height
            max_size = 1 << (max_h - 1) if max_h > 0 else 0
            if max_h > 0 and size - idx >= max_size:
                self._push_subtree(new_leaves[idx:idx+max_size])
                idx += max_size
            else:
                break
        # fill in rest of tree in one go, now that we can
        if idx < size:
            root_hash, hashes = self.__hasher._hash_full(new_leaves, idx, size)
            self._update(final_size, self.hashes + hashes)
        assert self.tree_size == final_size

    def extended(self, new_leaves):
        """Returns a new tree equal to this tree extended with new_leaves."""
        new_tree = self.__copy__()
        new_tree.extend(new_leaves)
        return new_tree

    def _calc_mth_hex(self, start, end):
        mth = self._calc_mth(start, end)
        return hexlify(mth)

    @functools.lru_cache(maxsize=256)
    def _calc_mth(self, start, end):
        if not end > start:
            raise ValueError("end must be greater than start")
        if (end - start) == 1:
            return self.hashStore.readLeaf(end)
        leafs, nodes = self.hashStore.getPath(end, start)
        leafHash = self.hashStore.readLeaf(end)
        hashes = [leafHash, ]
        for h in leafs:
            hashes.append(self.hashStore.readLeaf(h))
        for h in nodes:
            hashes.append(self.hashStore.readNode(h)[2])
        foldedHash = self.__hasher._hash_fold(hashes[::-1])
        return foldedHash

    def consistency_proof(self, first, second):
        return [self._calc_mth(a, b) for a, b in
                self._subproof(first, 0, second, True)]
        # return [base64.b64encode(self._calc_mth(a, b)) for a, b in
        #         self._subproof(first, 0, second, True)]
        # proof = []
        # for a, b in self._subproof(first, 0, second, True):
        #     mth = self._calc_mth(a, b)
        #     proof.append(mth)
        # return proof

    def inclusion_proof(self, start, end):
        return [self._calc_mth(a, b) for a, b in
                self._path(start, 0, end)]
        # return [base64.b64encode(self._calc_mth(a, b)) for a, b in
        #         self._path(start, 0, end)]
        # proof = []
        # for a, b in self._path(start, 0, end):
        #     mth = hexlify(self._calc_mth(a, b))
        #     proof.append(mth)
        # return proof

    def _subproof(self, m, start_n, end_n, b):
        n = end_n - start_n
        if m == n:
            if b:
                return []
            else:
                return [(start_n, end_n)]
        else:
            k = 1 << (len(bin(n - 1)) - 3)
            if m <= k:
                return self._subproof(m, start_n, start_n + k, b) + [
                    (start_n + k, end_n)]
            else:
                return self._subproof(m - k, start_n + k, end_n, False) + [
                    (start_n, start_n + k)]

    def _path(self, m, start_n, end_n):
        n = end_n - start_n
        if n == 1:
            return []
        else:
            # `k` is the largest power of 2 less than `n`
            k = 1 << (len(bin(n - 1)) - 3)
            if m < k:
                return self._path(m, start_n, start_n + k) + [
                    (start_n + k, end_n)]
            else:
                return self._path(m - k, start_n + k, end_n) + [
                    (start_n, start_n + k)]

    def get_tree_head(self, seq=None):
        if seq is None:
            seq = self.tree_size
        if seq > self.tree_size:
            raise IndexError
        return {
            'tree_size': seq,
            'sha256_root_hash': self._calc_mth(0, seq) if seq else None,
        }


class MerkleVerifier(object):
    """A utility class for doing Merkle path computations."""

    def __init__(self, hasher=TreeHasher()):
        self.hasher = hasher

    def __repr__(self):
        return "%r(hasher: %r)" % (self.__class__.__name__, self.hasher)

    def __str__(self):
        return "%s(hasher: %s)" % (self.__class__.__name__, self.hasher)

    @error.returns_true_or_raises
    def verify_tree_consistency(self, old_tree_size, new_tree_size, old_root,
                                new_root, proof):
        """Verify the consistency between two root hashes.

        old_tree_size must be <= new_tree_size.

        Args:
            old_tree_size: size of the older tree.
            new_tree_size: size of the newer_tree.
            old_root: the root hash of the older tree.
            new_root: the root hash of the newer tree.
            proof: the consistency proof.

        Returns:
            True. The return value is enforced by a decorator and need not be
                checked by the caller.

        Raises:
            ConsistencyError: the proof indicates an inconsistency
                (this is usually really serious!).
            ProofError: the proof is invalid.
            ValueError: supplied tree sizes are invalid.
        """
        old_size = old_tree_size
        new_size = new_tree_size

        if old_size < 0 or new_size < 0:
            raise ValueError("Negative tree size")

        if old_size > new_size:
            raise ValueError("Older tree has bigger size (%d vs %d), did "
                             "you supply inputs in the wrong order?" %
                             (old_size, new_size))

        if old_size == new_size:
            if old_root == new_root:
                if proof:
                    logging.warning("Trees are identical, ignoring proof")
                return True
            else:
                raise error.ConsistencyError("Inconsistency: different root "
                                             "hashes for the same tree size")

        if old_size == 0:
            if proof:
                # A consistency proof with an empty tree is an empty proof.
                # Anything is consistent with an empty tree, so ignore whatever
                # bogus proof was supplied. Note we do not verify here that the
                # root hash is a valid hash for an empty tree.
                logging.warning("Ignoring non-empty consistency proof for "
                                "empty tree.")
            return True

        # Now 0 < old_size < new_size
        # A consistency proof is essentially an audit proof for the node with
        # index old_size - 1 in the newer tree. The sole difference is that
        # the path is already hashed together into a single hash up until the
        # first audit node that occurs in the newer tree only.
        node = old_size - 1
        last_node = new_size - 1

        # While we are the right child, everything is in both trees, so move one
        # level up.
        while node % 2:
            node //= 2
            last_node //= 2

        p = iter(proof)
        try:
            if node:
                # Compute the two root hashes in parallel.
                new_hash = old_hash = next(p)
            else:
                # The old tree was balanced (2**k nodes), so we already have
                # the first root hash.
                new_hash = old_hash = old_root

            while node:
                if node % 2:
                    # node is a right child: left sibling exists in both trees.
                    next_node = next(p)
                    old_hash = self.hasher.hash_children(next_node, old_hash)
                    new_hash = self.hasher.hash_children(next_node, new_hash)
                elif node < last_node:
                    # node is a left child: right sibling only exists in the
                    # newer tree.
                    new_hash = self.hasher.hash_children(new_hash, next(p))
                # else node == last_node: node is a left child with no sibling
                # in either tree.
                node //= 2
                last_node //= 2

            # Now old_hash is the hash of the first subtree. If the two trees
            # have different height, continue the path until the new root.
            while last_node:
                n = next(p)
                new_hash = self.hasher.hash_children(new_hash, n)
                last_node //= 2

            # If the second hash does not match, the proof is invalid for the
            # given pair. If, on the other hand, the newer hash matches but the
            # older one doesn't, then the proof (together with the signatures
            # on the hashes) is proof of inconsistency.
            # Continue to find out.
            # if new_hash != new_root:
            #     raise error.ProofError("Bad Merkle proof: second root hash "
            #                            "does not match. Expected hash: %s "
            #                            ", computed hash: %s" %
            #                            (b64encode(new_root).strip(),
            #                             b64encode(new_hash).strip()))
            # elif old_hash != old_root:
            #     raise error.ConsistencyError("Inconsistency: first root hash "
            #                                  "does not match. Expected hash: "
            #                                  "%s, computed hash: %s" %
            #                                  (b64encode(old_root).strip(),
            #                                   b64encode(old_hash).strip())
            #                                  )
            if new_hash != new_root:
                raise error.ProofError("Bad Merkle proof: second root hash "
                                       "does not match. Expected hash: %s "
                                       ", computed hash: %s" %
                                       (hexlify(new_root).strip(),
                                        hexlify(new_hash).strip()))
            elif old_hash != old_root:
                raise error.ConsistencyError("Inconsistency: first root hash "
                                             "does not match. Expected hash: "
                                             "%s, computed hash: %s" %
                                             (hexlify(old_root).strip(),
                                              hexlify(old_hash).strip())
                                             )

        except StopIteration:
            raise error.ProofError("Merkle proof is too short")

        # We've already verified consistency, so accept the proof even if
        # there's garbage left over (but log a warning).
        try:
            next(p)
        except StopIteration:
            pass
        else:
            logging.warning("Proof has extra nodes")
        return True

    def _calculate_root_hash_from_audit_path(self, leaf_hash, node_index,
                                             audit_path, tree_size):
        calculated_hash = leaf_hash
        last_node = tree_size - 1
        while last_node > 0:
            if not audit_path:
                raise error.ProofError('Proof too short: left with node index '
                                       '%d' % node_index)
            if node_index % 2:
                audit_hash = audit_path.pop(0)
                calculated_hash = self.hasher.hash_children(
                    audit_hash, calculated_hash)
            elif node_index < last_node:
                audit_hash = audit_path.pop(0)
                calculated_hash = self.hasher.hash_children(
                    calculated_hash, audit_hash)
            # node_index == last_node and node_index is even: A sibling does
            # not exist. Go further up the tree until node_index is odd so
            # calculated_hash will be used as the right-hand operand.
            node_index //= 2
            last_node //= 2
        if audit_path:
            raise error.ProofError('Proof too long: Left with %d hashes.' %
                                   len(audit_path))
        return calculated_hash

    @classmethod
    def audit_path_length(cls, index, tree_size):
        length = 0
        last_node = tree_size - 1
        while last_node > 0:
            if index % 2 or index < last_node:
                length += 1
            index //= 2
            last_node //= 2

        return length

    @error.returns_true_or_raises
    def verify_leaf_hash_inclusion(self, leaf_hash, leaf_index, proof, sth):
        """Verify a Merkle Audit Path.

        See section 2.1.1 of RFC6962 for the exact path description.

        Args:
            leaf_hash: The hash of the leaf for which the proof was provided.
            leaf_index: Index of the leaf in the tree.
            proof: A list of SHA-256 hashes representing the  Merkle audit path.
            sth: STH with the same tree size as the one used to fetch the proof.
            The sha256_root_hash from this STH will be compared against the
            root hash produced from the proof.

        Returns:
            True. The return value is enforced by a decorator and need not be
                checked by the caller.

        Raises:
            ProofError: the proof is invalid.
        """
        leaf_index = int(leaf_index)
        tree_size = int(sth.tree_size)
        #TODO(eranm): Verify signature over STH
        if tree_size <= leaf_index:
            raise ValueError("Provided STH is for a tree that is smaller "
                             "than the leaf index. Tree size: %d Leaf "
                             "index: %d" % (tree_size, leaf_index))
        if tree_size < 0 or leaf_index < 0:
            raise ValueError("Negative tree size or leaf index: "
                                   "Tree size: %d Leaf index: %d" %
                                   (tree_size, leaf_index))
        calculated_root_hash = self._calculate_root_hash_from_audit_path(
                leaf_hash, leaf_index, proof[:], tree_size)
        if calculated_root_hash == sth.sha256_root_hash:
            return True

        # raise error.ProofError("Constructed root hash differs from provided "
        #                        "root hash. Constructed: %s Expected: %s" %
        #                        (b64encode(calculated_root_hash).strip(),
        #                         b64encode(sth.sha256_root_hash).strip()))
        raise error.ProofError("Constructed root hash differs from provided "
                               "root hash. Constructed: %s Expected: %s" %
                               (hexlify(calculated_root_hash).strip(),
                                hexlify(sth.sha256_root_hash).strip()))

    @error.returns_true_or_raises
    def verify_leaf_inclusion(self, leaf, leaf_index, proof, sth):
        """Verify a Merkle Audit Path.

        See section 2.1.1 of RFC6962 for the exact path description.

        Args:
            leaf: The leaf for which the proof was provided.
            leaf_index: Index of the leaf in the tree.
            proof: A list of SHA-256 hashes representing the  Merkle audit path.
            sth: STH with the same tree size as the one used to fetch the proof.
            The sha256_root_hash from this STH will be compared against the
            root hash produced from the proof.

        Returns:
            True. The return value is enforced by a decorator and need not be
                checked by the caller.

        Raises:
            ProofError: the proof is invalid.
        """
        leaf_hash = self.hasher.hash_leaf(leaf)
        return self.verify_leaf_hash_inclusion(leaf_hash, leaf_index, proof,
                                               sth)
