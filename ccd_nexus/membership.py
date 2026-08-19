"""Stake-weighted membership and Sybil-budget checks for the test network."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crypto import KeyPair, canonical_bytes, digest


class MembershipError(ValueError):
    """Raised when a membership or stake rule is violated."""


@dataclass(frozen=True)
class AdmissionCertificate:
    certificate_id: str
    epoch: int
    validator_id: str
    public_key: bytes
    deposit_id: str
    stake: int
    signatory: str
    authority_signature: bytes
    statement_digest: str


@dataclass
class MembershipRegistry:
    authority_keypair: KeyPair
    min_stake: int
    epoch: int = 0
    records: dict[str, AdmissionCertificate] = field(default_factory=dict)
    used_deposits: set[str] = field(default_factory=set)

    @property
    def authority_id(self) -> str:
        return self.authority_keypair.identity

    @property
    def total_stake(self) -> int:
        return sum(record.stake for record in self.records.values())

    @property
    def threshold(self) -> int:
        return (2 * self.total_stake) // 3 + 1

    def _statement(
        self,
        validator_id: str,
        public_key: bytes,
        deposit_id: str,
        stake: int,
    ) -> dict:
        return {
            "protocol": "CCD/NEXUS/v1",
            "phase": "ADMISSION",
            "epoch": self.epoch,
            "validator_id": validator_id,
            "public_key": public_key.hex(),
            "deposit_id": deposit_id,
            "stake": stake,
            "authority": self.authority_id,
        }

    def admit(
        self,
        *,
        validator_id: str,
        public_key: bytes,
        deposit_id: str,
        stake: int,
    ) -> AdmissionCertificate:
        if validator_id in self.records:
            raise MembershipError("validator identity already exists")
        if deposit_id in self.used_deposits:
            raise MembershipError("deposit id has already been used")
        if stake < self.min_stake:
            raise MembershipError("stake is below minimum")
        if not validator_id or not deposit_id or not public_key:
            raise MembershipError("identity, deposit and public key are required")
        statement = self._statement(validator_id, public_key, deposit_id, stake)
        statement_digest = digest(statement)
        signature = self.authority_keypair.sign(canonical_bytes(statement))
        certificate_id = digest(
            {
                "statement": statement_digest,
                "authority_signature": signature.hex(),
            }
        )
        certificate = AdmissionCertificate(
            certificate_id=certificate_id,
            epoch=self.epoch,
            validator_id=validator_id,
            public_key=public_key,
            deposit_id=deposit_id,
            stake=stake,
            signatory=self.authority_id,
            authority_signature=signature,
            statement_digest=statement_digest,
        )
        if not self.verify_certificate(certificate):
            raise MembershipError("issued admission certificate failed verification")
        self.records[validator_id] = certificate
        self.used_deposits.add(deposit_id)
        return certificate

    def verify_certificate(self, certificate: AdmissionCertificate) -> bool:
        statement = self._statement(
            certificate.validator_id,
            certificate.public_key,
            certificate.deposit_id,
            certificate.stake,
        )
        expected_digest = digest(statement)
        expected_id = digest(
            {
                "statement": expected_digest,
                "authority_signature": certificate.authority_signature.hex(),
            }
        )
        return (
            certificate.certificate_id == expected_id
            and certificate.statement_digest == expected_digest
            and certificate.epoch == self.epoch
            and certificate.signatory == self.authority_id
            and certificate.stake >= self.min_stake
            and KeyPair.verify(
                self.authority_keypair.public_key,
                canonical_bytes(statement),
                certificate.authority_signature,
            )
        )

    def register_external_certificate(self, certificate: AdmissionCertificate) -> None:
        if not self.verify_certificate(certificate):
            raise MembershipError("invalid admission certificate")
        if certificate.validator_id in self.records:
            raise MembershipError("validator identity already exists")
        if certificate.deposit_id in self.used_deposits:
            raise MembershipError("deposit id has already been used")
        self.records[certificate.validator_id] = certificate
        self.used_deposits.add(certificate.deposit_id)

    def sybil_capacity(self, budget: int) -> int:
        if budget < 0:
            raise MembershipError("budget cannot be negative")
        return budget // self.min_stake

    def weight_of(self, validator_ids: set[str]) -> int:
        unknown = validator_ids - set(self.records)
        if unknown:
            raise MembershipError(f"unknown validators: {sorted(unknown)}")
        return sum(self.records[item].stake for item in validator_ids)

    def split_budget(self, budget: int, requested_identities: int) -> tuple[int, ...]:
        if requested_identities <= 0:
            raise MembershipError("requested identities must be positive")
        if self.sybil_capacity(budget) < requested_identities:
            raise MembershipError("budget cannot fund requested identities")
        base = budget // requested_identities
        remainder = budget % requested_identities
        return tuple(base + (1 if index < remainder else 0) for index in range(requested_identities))
