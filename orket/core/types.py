from enum import Enum

class CardType(str, Enum):
    ROCK = "rock"
    EPIC = "epic"
    ISSUE = "issue"
    UTILITY = "utility"
    APP = "app"

class CardStatus(str, Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING_FOR_DEVELOPER = "waiting_for_developer" # Waiting on external input/dependency
    READY_FOR_TESTING = "ready_for_testing"
    CODE_REVIEW = "code_review"
    AWAITING_GUARD_REVIEW = "awaiting_guard_review"
    GUARD_APPROVED = "guard_approved"
    GUARD_REJECTED = "guard_rejected"
    GUARD_REQUESTED_CHANGES = "guard_requested_changes"
    DONE = "done"
    CANCELED = "canceled"
    ARCHIVED = "archived"

class WaitReason(str, Enum):
    RESOURCE = "resource"       # Waiting on a specific person/role
    DEPENDENCY = "dependency"   # Waiting on another task/card
    REVIEW = "review"           # Waiting on approval/feedback
    INPUT = "input"             # Waiting on external information/clarification
    SYSTEM = "system"           # Waiting on system availability/capacity
