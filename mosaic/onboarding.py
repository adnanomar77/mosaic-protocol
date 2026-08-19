"""Permissionless onboarding primitives for MOSAIC testnet."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Iterable

from ccd_nexus.crypto import digest

from .economics import SettlementError, SettlementLedger
from .membership import (
    AdmissionCertificate,
    AdmissionRequest,
    MembershipError,
    MembershipManager,
    StakeBond,
)


class OnboardingError(ValueError):
    pass


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise OnboardingError("invalid base64 onboarding field") from exc


def admission_to_wire(request: AdmissionRequest) -> dict:
    return {
        "validator_id": request.validator_id,
        "public_key": _b64(request.public_key),
        "stake": request.stake,
        "deposit_id": request.deposit_id,
        "requested_epoch": request.requested_epoch,
        "applicant_signature": _b64(request.applicant_signature),
        "bond_id": request.bond_id,
    }


def admission_from_wire(data: dict) -> AdmissionRequest:
    return AdmissionRequest(
        validator_id=data["validator_id"],
        public_key=_unb64(data["public_key"]),
        stake=int(data["stake"]),
        deposit_id=data["deposit_id"],
        requested_epoch=int(data["requested_epoch"]),
        applicant_signature=_unb64(data["applicant_signature"]),
        bond_id=data.get("bond_id"),
    )


def bond_to_wire(bond: StakeBond) -> dict:
    return {
        "bond_id": bond.bond_id,
        "owner": bond.owner,
        "owner_public_key": _b64(bond.owner_public_key),
        "amount": bond.amount,
        "asset": bond.asset,
        "activation_epoch": bond.activation_epoch,
        "unlock_epoch": bond.unlock_epoch,
        "owner_signature": _b64(bond.owner_signature),
    }


def bond_from_wire(data: dict) -> StakeBond:
    return StakeBond(
        bond_id=data["bond_id"],
        owner=data["owner"],
        owner_public_key=_unb64(data["owner_public_key"]),
        amount=int(data["amount"]),
        asset=data["asset"],
        activation_epoch=int(data["activation_epoch"]),
        unlock_epoch=int(data["unlock_epoch"]),
        owner_signature=_unb64(data["owner_signature"]),
    )


def admission_certificate_to_wire(certificate: AdmissionCertificate) -> dict:
    return {
        "request_digest": certificate.request_digest,
        "epoch": certificate.epoch,
        "approver_ids": list(certificate.approver_ids),
        "signatures": [_b64(item) for item in certificate.signatures],
        "certificate_id": certificate.certificate_id,
    }


@dataclass
class AdmissionCoordinator:
    """Durable admission gate reused by every testnet onboarding endpoint."""

    membership: MembershipManager
    settlement: SettlementLedger
    store: object | None = None

    def admit(
        self,
        request: AdmissionRequest,
        bond: StakeBond,
        approver_ids: Iterable[str] = (),
    ) -> AdmissionCertificate:
        if not request.verify():
            raise OnboardingError("invalid applicant signature")
        if not bond.verify():
            raise OnboardingError("invalid stake bond signature")
        if request.bond_id != bond.bond_id:
            raise OnboardingError("request and bond ids do not match")
        if request.public_key != bond.owner_public_key or request.stake != bond.amount:
            raise OnboardingError("request and bond owner or amount mismatch")
        if self.settlement.balance_of(bond.owner) < bond.amount:
            raise OnboardingError("applicant has insufficient settled balance")
        try:
            certificate = self.membership.admit(request, approver_ids=approver_ids, bond=bond)
        except (MembershipError, SettlementError) as exc:
            raise OnboardingError(str(exc)) from exc
        if self.store is None:
            raise OnboardingError("onboarding coordinator is not bound to durable store")
        self.settlement.persist(self.store)
        self.store.put(
            "onboarding",
            certificate.certificate_id,
            {
                "protocol": "MOSAIC/ONBOARDING/v1",
                "request": admission_to_wire(request),
                "bond": bond_to_wire(bond),
                "certificate": admission_certificate_to_wire(certificate),
                "state_root": self.settlement.state_root,
                "membership_root": self.membership.snapshot.root,
            },
            event=True,
        )
        return certificate

    def bind_store(self, store: object) -> "AdmissionCoordinator":
        self.store = store
        return self

    def restore_from_store(self) -> int:
        if self.store is None:
            raise OnboardingError("onboarding coordinator is not bound to durable store")
        restored = 0
        for _, payload in self.store.items("onboarding"):
            request = admission_from_wire(payload["request"])
            bond = bond_from_wire(payload["bond"])
            self.membership.restore_admission(request, bond)
            restored += 1
        expected = self.onboarding_root if restored else None
        if restored and expected != digest(
            {
                "membership_root": self.membership.snapshot.root,
                "settlement_root": self.settlement.state_root,
            }
        ):
            raise OnboardingError("restored onboarding root mismatch")
        return restored

    @property
    def onboarding_root(self) -> str:
        return digest(
            {
                "membership_root": self.membership.snapshot.root,
                "settlement_root": self.settlement.state_root,
            }
        )
