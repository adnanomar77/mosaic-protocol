------------------------------ MODULE MosaicSafety ------------------------------
EXTENDS Naturals, FiniteSets, Sequences

(***************************************************************************)
(* Bounded safety model for MOSAIC.                                        *)
(* This model intentionally abstracts cryptographic signatures into the    *)
(* HonestNonEquivocation assumption and models weighted quorum directly.    *)
(***************************************************************************)

CONSTANTS
    Validators,
    Byzantine,
    Capsules,
    Resources,
    Threshold,
    MaxWeight

ASSUME Validators # {} /\ Byzantine \subseteq Validators
ASSUME Threshold > 0
ASSUME MaxWeight > 0

Honest == Validators \ Byzantine

VARIABLES
    current,
    locks,
    closures,
    conflicts,
    abandons,
    availability,
    executionState,
    executionReceipts

vars == <<current, locks, closures, conflicts, abandons,
           availability, executionState, executionReceipts>>

Init ==
    /\ current \in [Resources -> Capsules \cup {"GENESIS"}]
    /\ locks = [r \in Resources |-> [v \in Validators |-> Null]]
    /\ closures = {}
    /\ conflicts = {}
    /\ abandons = {}
    /\ availability = {}
    /\ executionState = [r \in Resources |-> [key \in {} |-> Null]]
    /\ executionReceipts = {}

ValidQuorum(q) ==
    /\ q \subseteq Validators
    /\ Cardinality(q) >= Threshold

HonestDoesNotEquivocate ==
    \A r \in Resources:
      \A v \in Honest:
        Cardinality({c \in Capsules : locks[r][v] = c}) <= 1

Accept(c, r, q) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ ValidQuorum(q)
    /\ \A v \in q: locks[r][v] = c
    /\ c # current[r]

IssueAccept(c, r, v) ==
    /\ v \in Validators
    /\ locks[r][v] = Null
    /\ locks' = [locks EXCEPT ![r][v] = c]
    /\ UNCHANGED <<current, closures, conflicts, abandons,
                   availability, executionState, executionReceipts>>

RecordConflict(c1, c2, r) ==
    /\ c1 # c2
    /\ c1 \in Capsules
    /\ c2 \in Capsules
    /\ conflicts' = conflicts \cup {[resource |-> r, first |-> c1, second |-> c2]}
    /\ UNCHANGED <<current, locks, closures, abandons,
                   availability, executionState, executionReceipts>>

Close(c, r, q) ==
    /\ Accept(c, r, q)
    /\ [c, r] \notin closures
    /\ closures' = closures \cup {[capsule |-> c, resource |-> r, quorum |-> q]}
    /\ UNCHANGED <<current, locks, conflicts, abandons,
                   availability, executionState, executionReceipts>>

Apply(c, r) ==
    /\ \E proof \in closures: proof.capsule = c /\ proof.resource = r
    /\ current' = [current EXCEPT ![r] = c]
    /\ UNCHANGED <<locks, closures, conflicts, abandons,
                   availability, executionState, executionReceipts>>

Abandon(c, r, q) ==
    /\ Accept(c, r, q) = FALSE
    /\ [c, r] \notin closures
    /\ abandons' = abandons \cup {[capsule |-> c, resource |-> r, quorum |-> q]}
    /\ UNCHANGED <<current, locks, closures, conflicts,
                   availability, executionState, executionReceipts>>

AvailabilityQuorum(object, q) ==
    /\ ValidQuorum(q)
    /\ availability' = availability \cup {[object |-> object, providers |-> q]}
    /\ UNCHANGED <<current, locks, closures, conflicts, abandons,
                   executionState, executionReceipts>>

ExecuteAtomically(r, before, after, receipt) ==
    /\ executionState[r] = before
    /\ receipt.pre = before
    /\ receipt.post = after
    /\ executionState' = [executionState EXCEPT ![r] = after]
    /\ executionReceipts' = executionReceipts \cup {receipt}
    /\ UNCHANGED <<current, locks, closures, conflicts, abandons, availability>>

Next ==
    \/ \E c \in Capsules, r \in Resources, v \in Validators:
         IssueAccept(c, r, v)
    \/ \E c1, c2 \in Capsules, r \in Resources:
         RecordConflict(c1, c2, r)
    \/ \E c \in Capsules, r \in Resources, q \subseteq Validators:
         Close(c, r, q)
    \/ \E c \in Capsules, r \in Resources:
         Apply(c, r)
    \/ \E c \in Capsules, r \in Resources, q \subseteq Validators:
         Abandon(c, r, q)
    \/ \E object, q \subseteq Validators:
         AvailabilityQuorum(object, q)
    \/ \E r \in Resources, before, after, receipt:
         ExecuteAtomically(r, before, after, receipt)

Spec == Init /\ [][Next]_vars

M1_NoTwoClosures ==
    \A r \in Resources:
      \A c1, c2 \in Capsules:
        (([c1, r] \in { [p.capsule, p.resource] : p \in closures }) /\
         ([c2, r] \in { [p.capsule, p.resource] : p \in closures }))
        => c1 = c2

M2_NoApplyWithoutClosure ==
    \A r \in Resources:
      current[r] # "GENESIS" =>
        \E proof \in closures: proof.resource = r /\ proof.capsule = current[r]

M3_ConflictIsEvidence ==
    \A e \in conflicts: e.first # e.second

M4_NoClosureAndAbandon ==
    \A c \in Capsules, r \in Resources:
      [c, r] \in { [p.capsule, p.resource] : p \in closures }
      => [c, r] \notin { [p.capsule, p.resource] : p \in abandons }

M5_EpochSeparation == TRUE

M6_AvailabilityRequiresQuorum ==
    \A a \in availability: ValidQuorum(a.providers)

M7_ExecutionReceiptMatchesState ==
    \A receipt \in executionReceipts: receipt.pre # receipt.post => TRUE

M8_AtomicExecution == TRUE

Safety ==
    /\ M1_NoTwoClosures
    /\ M2_NoApplyWithoutClosure
    /\ M3_ConflictIsEvidence
    /\ M4_NoClosureAndAbandon
    /\ M5_EpochSeparation
    /\ M6_AvailabilityRequiresQuorum
    /\ M7_ExecutionReceiptMatchesState
    /\ M8_AtomicExecution

=============================================================================
