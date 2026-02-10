from pydantic import BaseModel, Field

class BottleneckThresholds(BaseModel):
    """
    Configuration for detecting bottlenecks in the workflow.
    Defined in core to ensure it's available to all layers.
    """
    blocked_duration_hours: int = Field(24, description="Hours a card can be blocked before alert")
    review_duration_hours: int = Field(48, description="Hours a card can be in review before alert")
    wip_limit_per_seat: int = Field(3, description="Max cards in progress per seat")
    queue_depth_per_seat: int = Field(5, description="Max cards ready for a seat")
