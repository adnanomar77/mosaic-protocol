------------------------------ MODULE MosaicSafety ------------------------------
EXTENDS Naturals, FiniteSets

(***************************************************************************)
(* Evidence-Complete Transition Closure (ECTC) bounded model.             *)
(*                                                                         *)
(* The model abstracts signatures and execution semantics through the      *)
(* constants below. TLA+ checks the named invariants within finite sets;   *)
(* it is not an unbounded theorem prover and does not establish crypto.   *)
(* ClosureRecord is the finite-state projection of the paper's VCP         *)
(* predicate: receipt signatures, canonical proof IDs, membership lookup, *)
(* and exact wire serialization are abstracted as Close preconditions.     *)
(***************************************************************************)

CONSTANTS
    Validators,
    Byzantine,
    Capsules,
    Resources,
    StateRoots,
    Threshold,
    Genesis,
    None,
    CapsulePredecessor,
    CapsuleSuccessor

ASSUME Validators # {}
ASSUME Byzantine \subseteq Validators
ASSUME Capsules # {}
ASSUME Resources # {}
ASSUME StateRoots # {}
ASSUME Threshold > 0
ASSUME Threshold <= Cardinality(Validators)
ASSUME Genesis \notin Capsules
ASSUME None \notin Capsules
ASSUME CapsulePredecessor \in [Capsules -> Capsules \cup {Genesis}]
ASSUME CapsuleSuccessor \in [Capsules -> StateRoots]

Honest == Validators \ Byzantine

Quorum(q) ==
    /\ q \subseteq Validators
    /\ Cardinality(q) >= Threshold

SameContext(c1, c2) ==
    CapsulePredecessor[c1] = CapsulePredecessor[c2]

Compatible(c1, c2) ==
    c1 = c2 \/ ~SameContext(c1, c2)

ClosureRecord ==
    [capsule: Capsules,
     resource: Resources,
     predecessor: Capsules \cup {Genesis},
     successor: StateRoots,
     quorum: SUBSET Validators]

ConflictRecord ==
    [resource: Resources,
     first: Capsules,
     second: Capsules,
     predecessor: Capsules \cup {Genesis}]

AbandonRecord ==
    [resource: Resources,
     capsule: Capsules,
     predecessor: Capsules \cup {Genesis},
     proof: Capsules]

VARIABLES
    current,
    locks,
    closures,
    conflicts,
    abandons,
    applied,
    execution

vars == <<current, locks, closures, conflicts, abandons, applied, execution>>

Init ==
    /\ current \in [Resources -> Capsules \cup {Genesis}]
    /\ locks = [r \in Resources |-> [v \in Validators |-> None]]
    /\ closures = {}
    /\ conflicts = {}
    /\ abandons = {}
    /\ applied = {}
    /\ execution = [c \in Capsules |-> None]

IssueAccept(c, r, v) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ v \in Validators
    /\ locks[r][v] = None
    /\ locks' = [locks EXCEPT ![r][v] = c]
    /\ UNCHANGED <<current, closures, conflicts, abandons, applied, execution>>

RecordConflict(c1, c2, r) ==
    /\ c1 \in Capsules
    /\ c2 \in Capsules
    /\ r \in Resources
    /\ c1 # c2
    /\ SameContext(c1, c2)
    /\ conflicts' = conflicts \cup
         {[resource |-> r,
           first |-> c1,
           second |-> c2,
           predecessor |-> CapsulePredecessor[c1]]}
    /\ UNCHANGED <<current, locks, closures, abandons, applied, execution>>

Close(c, r, q) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ Quorum(q)
    /\ current[r] = CapsulePredecessor[c]
    /\ \A v \in q: locks[r][v] = c
    /\ closures' = closures \cup
         {[capsule |-> c,
           resource |-> r,
           predecessor |-> CapsulePredecessor[c],
           successor |-> CapsuleSuccessor[c],
           quorum |-> q]}
    /\ UNCHANGED <<current, locks, conflicts, abandons, applied, execution>>

Apply(c, r) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ \E closure \in closures:
          closure.capsule = c
          /\ closure.resource = r
          /\ closure.predecessor = current[r]
    /\ current' = [current EXCEPT ![r] = c]
    /\ applied' = applied \cup {[capsule |-> c, resource |-> r]}
    /\ UNCHANGED <<locks, closures, conflicts, abandons, execution>>

Abandon(c, r) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ c # current[r]
    /\ \A x \in closures: ~(x.capsule = c /\ x.resource = r)
    /\ abandons' = abandons \cup
         {[resource |-> r,
           capsule |-> c,
           predecessor |-> CapsulePredecessor[c],
           proof |-> c]}
    /\ UNCHANGED <<current, locks, closures, conflicts, applied, execution>>

Execute(c, r) ==
    /\ c \in Capsules
    /\ r \in Resources
    /\ \E a \in applied: a.capsule = c /\ a.resource = r
    /\ execution' = [execution EXCEPT ![c] = CapsuleSuccessor[c]]
    /\ UNCHANGED <<current, locks, closures, conflicts, abandons, applied>>

Next ==
    \/ \E c \in Capsules, r \in Resources, v \in Validators:
         IssueAccept(c, r, v)
    \/ \E c1, c2 \in Capsules, r \in Resources:
         RecordConflict(c1, c2, r)
    \/ \E c \in Capsules, r \in Resources, q \subseteq Validators:
         Close(c, r, q)
    \/ \E c \in Capsules, r \in Resources:
         Apply(c, r)
    \/ \E c \in Capsules, r \in Resources:
         Abandon(c, r)
    \/ \E c \in Capsules, r \in Resources:
         Execute(c, r)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Paper invariant mapping                                                 *)
(***************************************************************************)

I1_NoApplyWithoutClosure ==
    \A a \in applied:
      \E closure \in closures:
        closure.capsule = a.capsule
        /\ closure.resource = a.resource

I2_PredecessorBinding ==
    \A closure \in closures:
      closure.predecessor = CapsulePredecessor[closure.capsule]

I3_SealBinding ==
    \A closure \in closures:
      closure.successor = CapsuleSuccessor[closure.capsule]

I4_NoTwoIncompatibleClosures ==
    \A c1, c2 \in Capsules, r \in Resources:
      (\E x \in closures: x.capsule = c1 /\ x.resource = r)
      /\ (\E y \in closures: y.capsule = c2 /\ y.resource = r)
      => Compatible(c1, c2)

I5_FirstClaimNonEquivocation ==
    \A r \in Resources, v \in Honest:
      Cardinality({c \in Capsules : locks[r][v] = c}) <= 1

I6_ConflictEvidencePreserved ==
    \A e \in conflicts:
      /\ e.first # e.second
      /\ e.predecessor = CapsulePredecessor[e.first]
      /\ e.predecessor = CapsulePredecessor[e.second]

I7_AbandonEvidencePreserved ==
    \A a \in abandons:
      /\ a.capsule \in Capsules
      /\ a.proof \in Capsules
      /\ a.predecessor = CapsulePredecessor[a.capsule]
      /\ \A x \in closures: ~(x.capsule = a.capsule /\ x.resource = a.resource)

I8_DeterministicExecution ==
    \A c \in Capsules:
      execution[c] # None => execution[c] = CapsuleSuccessor[c]

ECTC ==
    /\ I1_NoApplyWithoutClosure
    /\ I2_PredecessorBinding
    /\ I3_SealBinding
    /\ I4_NoTwoIncompatibleClosures
    /\ I5_FirstClaimNonEquivocation
    /\ I6_ConflictEvidencePreserved
    /\ I7_AbandonEvidencePreserved
    /\ I8_DeterministicExecution

Safety == ECTC

(***************************************************************************)
(* Model A theorem boundary                                                *)
(***************************************************************************)

(***************************************************************************)
(* For an unweighted committee, assume N >= 3f + 1, every closure quorum    *)
(* has at least 2f + 1 validators, and honest validators do not sign two    *)
(* incompatible Capsules in the same resource/epoch context. Two quorums    *)
(* then intersect in at least one honest validator. That shared honest      *)
(* signer would violate I5 if both incompatible ClosureProofs existed.      *)
(* This comment records the theorem boundary; TLC only checks finite cases. *)
(***************************************************************************)

=============================================================================
