from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from orket.core.domain.execution import ExecutionTurn


class ViolationCode(Enum):
    ROOT_FILE_VIOLATION = "ROOT_FILE_VIOLATION"
    CATEGORY_VIOLATION = "CATEGORY_VIOLATION"
    NAMING_VIOLATION = "NAMING_VIOLATION"


@dataclass
class iDesignViolation:
    code: ViolationCode
    severity: str
    message: str
    path: str


class iDesignValidator:
    """
    Mechanical Enforcer for iDesign structural integrity.

    Verifies that files created by agents follow the iDesign architectural
    pattern, ensuring components are properly categorized and named.
    """

    # Standard iDesign component categories.
    # Any file creation outside these directories (or product/src equivalents)
    # will be flagged as a violation.
    ALLOWED_CATEGORIES = {
        "managers",
        "engines",
        "accessors",
        "utils",
        "controllers",
        "tests",
        "schemas",
        "models",
        "infrastructure",
        "services",
        "agent_output",  # Standard Orket output directory
        "verification",  # Standard Orket verification directory
    }

    def __init__(self, organization: Any | None = None) -> None:
        self.allowed_categories = _resolve_allowed_categories(organization)

    def validate_turn(
        self,
        turn: ExecutionTurn | Path,
        workspace_root: Path | None = None,
    ) -> list[iDesignViolation]:
        """
        Scans tool calls in a turn for file creations and verifies their placement.
        Returns a list of structured violations.
        """
        if isinstance(self, iDesignValidator):
            validator = self
            actual_turn = turn
            actual_workspace_root = workspace_root
        else:
            validator = iDesignValidator()
            actual_turn = self
            actual_workspace_root = turn
        if not isinstance(actual_turn, ExecutionTurn):
            raise TypeError("validate_turn requires an ExecutionTurn")
        if actual_workspace_root is None:
            raise TypeError("validate_turn requires a workspace root")
        del actual_workspace_root
        violations = []
        for call in actual_turn.tool_calls:
            if call.tool == "write_file":
                path_str = call.args.get("path")
                if not path_str:
                    continue

                # Normalize path relative to workspace
                p = Path(path_str)
                parts = p.parts
                if not parts:
                    continue

                # Check for root files
                if len(parts) == 1 and p.suffix in {".py", ".ts", ".js"}:
                    violations.append(
                        iDesignViolation(
                            code=ViolationCode.ROOT_FILE_VIOLATION,
                            severity="error",
                            message=(
                                f"Source file '{path_str}' created in root. "
                                "Code must be encapsulated in a component directory."
                            ),
                            path=path_str,
                        )
                    )

                # Determine category
                category = parts[0].lower()
                if category in {"product", "src"} and len(parts) > 1:
                    category = parts[1].lower()
                    if category == "product" and len(parts) > 2:
                        category = parts[2].lower()

                if category not in validator.allowed_categories:
                    # Only enforce categorization for source code
                    if p.suffix in {".py", ".ts", ".js"}:
                        violations.append(
                            iDesignViolation(
                                code=ViolationCode.CATEGORY_VIOLATION,
                                severity="error",
                                message=(
                                    f"Unrecognized component category '{category}'. "
                                    "Source code must be in an allowed category."
                                ),
                                path=path_str,
                            )
                        )
                    continue  # No need to check naming if category is invalid or it's a non-code file

                # --- NAMING CONVENTION ENFORCEMENT ---
                filename = p.name.lower()
                if category == "managers" and "manager" not in filename:
                    violations.append(
                        iDesignViolation(
                            code=ViolationCode.NAMING_VIOLATION,
                            severity="error",
                            message=f"Manager component '{path_str}' must include 'Manager' in the filename.",
                            path=path_str,
                        )
                    )

                if category == "engines" and "engine" not in filename:
                    violations.append(
                        iDesignViolation(
                            code=ViolationCode.NAMING_VIOLATION,
                            severity="error",
                            message=f"Engine component '{path_str}' must include 'Engine' in the filename.",
                            path=path_str,
                        )
                    )

                if category == "accessors" and "accessor" not in filename:
                    violations.append(
                        iDesignViolation(
                            code=ViolationCode.NAMING_VIOLATION,
                            severity="error",
                            message=f"Accessor component '{path_str}' must include 'Accessor' in the filename.",
                            path=path_str,
                        )
                    )

        return violations


def _resolve_allowed_categories(organization: Any | None) -> set[str]:
    configured = getattr(organization, "allowed_idesign_categories", None) if organization is not None else None
    if configured is None:
        return set(iDesignValidator.ALLOWED_CATEGORIES)
    allowed = {str(category).strip().lower() for category in list(configured or []) if str(category).strip()}
    return allowed or set(iDesignValidator.ALLOWED_CATEGORIES)
