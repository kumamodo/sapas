from dataclasses import dataclass


@dataclass(frozen=True)
class TestStep:
    """Data representation of an executable test sequence item parsed from flow files."""
    item_id: str
    runner_index: str
    item_label: str
    flow_item: str
    command: str
