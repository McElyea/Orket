"""Fixed inputs shared by value and real filesystem boundary proof."""

from orket.core.domain.reconciler import StructuralAsset

TIMESTAMP = "2026-09-14T12:00:00+00:00"
BOARD_ASSETS = (
    StructuralAsset("core", "rocks", "run_the_business", '{"epics": []}'),
    StructuralAsset("core", "epics", "unplanned_support", '{"issues": []}'),
    StructuralAsset("product", "epics", "product_plan", '{"issues": [{"id": "linked"}]}'),
    StructuralAsset("product", "issues", "linked", '{"id": "linked", "summary": "Already linked"}'),
    StructuralAsset("product", "issues", "orphan", '{"id": "orphan", "summary": "Unplanned work"}'),
)
