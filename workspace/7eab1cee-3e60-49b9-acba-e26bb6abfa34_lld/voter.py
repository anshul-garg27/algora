import threading
from enum import Enum
from collections import defaultdict


class VoteError(Exception):
    pass


class Candidate:
    def __init__(self, cid, name, party):
        self.id = cid
        self.name = name
        self.party = party

    def __repr__(self):
        return f"{self.name}({self.party})"


class Voter:
    def __init__(self, vid, name, district_id):
        self.id = vid
        self.name = name
        self.district_id = district_id
        self.has_voted = False


class EVM:
    """One ballot box bound to a district. Thread-safe, append-only tally."""
    def __init__(self, evm_id, district_id, candidate_ids):
        self.id = evm_id
        self.district_id = district_id
        self._valid = set(candidate_ids)
        self._tally = defaultdict(int)
        self._sealed = False
        self._lock = threading.RLock()

    def cast(self, candidate_id):
        with self._lock:
            if self._sealed:
                raise VoteError(f"EVM {self.id} is sealed; polling closed")
            if candidate_id not in self._valid:
                raise VoteError(f"Candidate {candidate_id} not on this EVM")
            self._tally[candidate_id] += 1

    def seal(self):
        with self._lock:
            self._sealed = True

    def counts(self):
        with self._lock:
            return dict(self._tally)


class District:
    def __init__(self, did, name):
        self.id = did
        self.name = name
        self.evms = {}

    def add_evm(self, evm):
        self.evms[evm.id] = evm

    def results(self):
        agg = defaultdict(int)
        for evm in self.evms.values():
            for cid, c in evm.counts().items():
                agg[cid] += c
        return dict(agg)


class Constituency:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name
        self.districts = {}

    def add_district(self, d):
        self.districts[d.id] = d

    def results(self):
        agg = defaultdict(int)
        for d in self.districts.values():
            for cid, c in d.results().items():
                agg[cid] += c
        return dict(agg)


class State:
    def __init__(self, sid, name):
        self.id = sid
        self.name = name
        self.constituencies = {}

    def add_constituency(self, c):
        self.constituencies[c.id] = c

    def results(self):
        agg = defaultdict(int)
        for c in self.constituencies.values():
            for cid, cnt in c.results().items():
                agg[cid] += cnt
        return dict(agg)


class ElectionCommission:
    """Orchestrator: owns registries, validates, routes votes."""
    def __init__(self):
        self.states = {}
        self.candidates = {}
        self.voters = {}
        self._evm_index = {}        # evm_id -> EVM
        self._district_index = {}   # district_id -> District
        self._district_evms = defaultdict(list)
        self._lock = threading.RLock()

    # --- configuration ---
    def add_state(self, s): self.states[s.id] = s
    def add_constituency(self, state_id, c):
        self.states[state_id].add_constituency(c)
    def add_district(self, state_id, const_id, d):
        self.states[state_id].constituencies[const_id].add_district(d)
        self._district_index[d.id] = d
    def add_candidate(self, c): self.candidates[c.id] = c

    def assign_evm(self, district_id, evm):
        if district_id not in self._district_index:
            raise VoteError(f"Unknown district {district_id}")
        self._district_index[district_id].add_evm(evm)
        self._evm_index[evm.id] = evm
        self._district_evms[district_id].append(evm)

    # --- voter registration ---
    def register_voter(self, voter):
        if voter.district_id not in self._district_index:
            raise VoteError(f"Cannot register: unknown district {voter.district_id}")
        if voter.id in self.voters:
            raise VoteError(f"Voter {voter.id} already registered")
        self.voters[voter.id] = voter

    # --- voting ---
    def cast_vote(self, voter_id, candidate_id, evm_id=None):
        with self._lock:  # atomic check-then-act on has_voted
            voter = self.voters.get(voter_id)
            if voter is None:
                raise VoteError(f"Voter {voter_id} not registered")
            if voter.has_voted:
                raise VoteError(f"Voter {voter_id} has already voted")
            evms = self._district_evms.get(voter.district_id)
            if not evms:
                raise VoteError(f"No EVM available in district {voter.district_id}")
            if evm_id is not None:
                evm = self._evm_index.get(evm_id)
                if evm is None or evm.district_id != voter.district_id:
                    raise VoteError("EVM not valid for this voter's district")
            else:
                evm = evms[0]
            evm.cast(candidate_id)   # may raise -> voter stays not-voted
            voter.has_voted = True
            return evm.id

    def close_polling(self):
        for evm in self._evm_index.values():
            evm.seal()

    def named(self, results):
        return {self.candidates[c].name: n for c, n in results.items()}


if __name__ == "__main__":
    ec = ElectionCommission()
    ec.add_candidate(Candidate("A", "Alice", "Blue"))
    ec.add_candidate(Candidate("B", "Bob", "Red"))

    ec.add_state(State("S1", "Karnataka"))
    ec.add_constituency("S1", Constituency("C1", "Bangalore-South"))
    ec.add_district("S1", "C1", District("D1", "Jayanagar"))
    ec.add_district("S1", "C1", District("D2", "BTM"))
    ec.assign_evm("D1", EVM("E1", "D1", ["A", "B"]))
    ec.assign_evm("D2", EVM("E2", "D2", ["A", "B"]))

    ec.register_voter(Voter("V1", "v1", "D1"))
    ec.register_voter(Voter("V2", "v2", "D1"))
    ec.register_voter(Voter("V3", "v3", "D2"))

    ec.cast_vote("V1", "A")
    ec.cast_vote("V2", "B")
    ec.cast_vote("V3", "A")

    # duplicate vote rejected
    try:
        ec.cast_vote("V1", "B"); assert False
    except VoteError: pass

    # unregistered voter
    try:
        ec.cast_vote("VX", "A"); assert False
    except VoteError: pass

    # invalid candidate on EVM
    try:
        ec.cast_vote("V3", "Z"); assert False  # V3 already voted actually
    except VoteError: pass

    # unknown district registration
    try:
        ec.register_voter(Voter("V9", "v9", "DX")); assert False
    except VoteError: pass

    # concurrency: 100 fresh voters in D1, only one EVM, race-free
    for i in range(100):
        ec.register_voter(Voter(f"P{i}", f"p{i}", "D1"))
    def worker(i):
        try: ec.cast_vote(f"P{i}", "A")
        except VoteError: pass
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads: t.start()
    for t in threads: t.join()

    ec.close_polling()
    # sealed EVM rejects further votes
    try:
        ec._evm_index["E1"].cast("A"); assert False
    except VoteError: pass

    print("State result:", ec.named(ec.states["S1"].results()))
    print("Constituency C1:", ec.named(ec.states["S1"].constituencies["C1"].results()))
    print("District D1:", ec.named(ec._district_index["D1"].results()))
    # 1 (V1) + 100 concurrent = 101 for A in D1; B=1
    assert ec._district_index["D1"].results()["A"] == 101
    print("All assertions passed.")
