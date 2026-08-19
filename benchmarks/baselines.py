"""Reference profiles used by the local benchmark report.

The literature fields are contextual metadata, not measurements produced by this
repository. They must not be mixed with local CCD/NEXUS timings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineProfile:
    name: str
    ordering: str
    fast_path: str
    local_measurement: bool
    source: str
    note: str


PROFILES = (
    BaselineProfile(
        name="CCD/NEXUS prototype",
        ordering="partial by domain; join for cross-domain operations",
        fast_path="local domain certificate",
        local_measurement=True,
        source="local implementation",
        note="Python prototype; no network transport and no permissionless committee selection.",
    ),
    BaselineProfile(
        name="HotStuff",
        ordering="global ordered BFT path",
        fast_path="leader-driven consensus",
        local_measurement=False,
        source="https://arxiv.org/abs/1803.05069",
        note="Literature profile only; reported results are not directly comparable.",
    ),
    BaselineProfile(
        name="Narwhal/Tusk",
        ordering="DAG dissemination plus consensus ordering",
        fast_path="asynchronous dissemination layer",
        local_measurement=False,
        source="https://arxiv.org/abs/2105.11827",
        note="Literature profile only; reported results are not directly comparable.",
    ),
    BaselineProfile(
        name="Sui Lutris-style hybrid",
        ordering="object-local fast path plus consensus for conflicts",
        fast_path="consensusless agreement for eligible operations",
        local_measurement=False,
        source="https://arxiv.org/abs/2310.18042",
        note="Literature profile only; use as closest architectural reference.",
    ),
)
