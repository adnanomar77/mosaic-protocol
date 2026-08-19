"""Evidence-Complete Transition Closure (ECTC) outcome types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ECTCStatus(str, Enum):
    """Terminal outcomes exposed by the MOSAIC transition lifecycle."""

    CLOSED = "Closed"
    CONFLICT = "Conflict"
    ABANDONED = "Abandoned"


@dataclass(frozen=True)
class TransitionOutcome:
    """A verifiable terminal outcome for one Capsule.

    ``CLOSED`` requires a ClosureProof and a successor StateSeal.  ``CONFLICT``
    requires one or more ConflictEvidence identifiers.  ``ABANDONED`` requires
    an AbandonProof identifier.  A ``None`` outcome means that the local node
    has not observed a terminal artifact yet; it is not silently classified as
    success or failure.
    """

    capsule_id: str
    predecessor_id: str
    status: ECTCStatus
    evidence_ids: tuple[str, ...]
    successor_seal_id: str | None = None
    conflicting_capsule_ids: tuple[str, ...] = ()

    def is_evidence_complete(self) -> bool:
        if self.status is ECTCStatus.CLOSED:
            return bool(self.evidence_ids and self.successor_seal_id)
        if self.status in {ECTCStatus.CONFLICT, ECTCStatus.ABANDONED}:
            return bool(self.evidence_ids)
        return False
