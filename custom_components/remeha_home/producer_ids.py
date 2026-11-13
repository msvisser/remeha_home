"""Stable identifiers for energy producers reported by Remeha."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection
import json
import logging

_LOGGER = logging.getLogger(__name__)


def is_valid_producer(producer: object) -> bool:
    """Ignore incomplete API placeholders rather than register phantom devices."""
    if not isinstance(producer, dict):
        return False

    instance = producer.get("instanceWithinDevice")
    valid_instance = (isinstance(instance, int) and not isinstance(instance, bool)) or (
        isinstance(instance, str) and instance.isdecimal()
    )
    producer_type = producer.get("producerType")
    energy_type = producer.get("energyType")
    return (
        valid_instance
        and isinstance(producer_type, str)
        and bool(producer_type.strip())
        and isinstance(energy_type, str)
        and bool(energy_type.strip())
    )


class ProducerIdResolver:
    """Assign producer IDs once and retain them across incomplete API responses."""

    def __init__(self, assignments: dict[str, str] | None = None) -> None:
        """Restore previously persisted producer identities and their IDs."""
        self.assignments = dict(assignments or {})
        self._warned_ambiguous_appliances: set[str] = set()
        self._warned_invalid_appliances: set[str] = set()

    @staticmethod
    def _identity(appliance_id: str, producer: dict) -> str:
        """Describe a producer without depending on its position in the API list."""
        return json.dumps(
            [
                appliance_id,
                producer["instanceWithinDevice"],
                producer.get("producerType"),
                producer.get("energyType"),
            ],
            separators=(",", ":"),
        )

    def get_id(self, appliance_id: str, producer: dict) -> str | None:
        """Return the stable ID previously assigned to a producer."""
        if not is_valid_producer(producer):
            return None
        return self.assignments.get(self._identity(appliance_id, producer))

    def resolve(
        self,
        appliance_id: str,
        producers: list[dict],
        *,
        appliance_type: str | None = None,
        existing_electric_legacy_ids: Collection[str] = (),
    ) -> tuple[list[tuple[dict, str]], bool]:
        """Register new producers, preserving IDs already assigned to others.

        Allocate the legacy instance-based ID where available. When an instance
        is shared, allocate a type-suffixed ID to the additional producer.
        Existing allocations never change when a producer temporarily disappears.
        """
        valid_producers = [item for item in producers if is_valid_producer(item)]
        if (
            len(valid_producers) != len(producers)
            and appliance_id not in self._warned_invalid_appliances
        ):
            _LOGGER.debug(
                "Ignoring incomplete energy producer records for appliance %s",
                appliance_id,
            )
            self._warned_invalid_appliances.add(appliance_id)

        identities = Counter(
            self._identity(appliance_id, item) for item in valid_producers
        )
        ambiguous = {key for key, count in identities.items() if count > 1}
        if ambiguous and appliance_id not in self._warned_ambiguous_appliances:
            _LOGGER.warning(
                "Multiple indistinguishable producers for appliance %s; "
                "skipping these records to avoid mixing energy statistics",
                appliance_id,
            )
            self._warned_ambiguous_appliances.add(appliance_id)

        # Electric producers are first so a newly discovered hybrid preserves
        # the historic heat pump ID, even if the API response order changes.
        ordered = sorted(
            (
                item
                for item in valid_producers
                if self._identity(appliance_id, item) not in ambiguous
            ),
            key=lambda item: (
                item.get("energyType") != "Electric",
                str(item["instanceWithinDevice"]),
                str(item.get("producerType") or ""),
            ),
        )
        used = set(self.assignments.values())
        changed = False
        result = []

        for producer in ordered:
            identity = self._identity(appliance_id, producer)
            producer_id = self.assignments.get(identity)
            if producer_id is None:
                legacy = f"{appliance_id}_{producer['instanceWithinDevice']}"
                # Reserve an existing electric entity's legacy ID only when it
                # really belongs to a heat pump. Other gas boilers must keep
                # their legacy ID, including on non-colliding hybrid systems.
                reserve_for_existing_heat_pump = (
                    appliance_type == "HeatPump"
                    and producer.get("energyType") == "NaturalGas"
                    and legacy in existing_electric_legacy_ids
                )
                if legacy not in used and not reserve_for_existing_heat_pump:
                    producer_id = legacy
                else:
                    producer_type = producer.get("producerType") or "Unknown"
                    suffix = "".join(
                        character if character.isalnum() else "_"
                        for character in producer_type
                    )
                    producer_id = f"{legacy}_{suffix}"
                    if producer_id in used:
                        _LOGGER.warning(
                            "Cannot allocate an unambiguous producer ID for "
                            "appliance %s, type %s; skipping it",
                            appliance_id,
                            producer_type,
                        )
                        continue

                self.assignments[identity] = producer_id
                used.add(producer_id)
                changed = True
            result.append((producer, producer_id))

        return result, changed
