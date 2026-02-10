from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from orket.domain.execution import ExecutionTurn

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
        "agent_output",   # Standard Orket output directory
        "verification"    # Standard Orket verification directory
    }

    @staticmethod
    def validate_turn(turn: ExecutionTurn, workspace_root: Path) -> List[iDesignViolation]:
        """
        Scans tool calls in a turn for file creations and verifies their placement.
        Returns a list of structured violations.
        """
        violations = []
        for call in turn.tool_calls:
            if call.tool == "write_file":
                path_str = call.args.get("path")
                if not path_str: continue
                
                # Normalize path relative to workspace
                p = Path(path_str)
                parts = p.parts
                if not parts: continue
                
                # Check for root files
                if len(parts) == 1:
                    if p.suffix in {".py", ".ts", ".js"}:
                        violations.append(iDesignViolation(
                            code=ViolationCode.ROOT_FILE_VIOLATION,
                            severity="error",
                            message=f"Source file '{path_str}' created in root. Code must be encapsulated in a component directory.",
                            path=path_str
                        ))
                
                # Determine category
                category = parts[0].lower()
                if category in {"product", "src"} and len(parts) > 1:
                    category = parts[1].lower()
                    if category == "product" and len(parts) > 2:
                        category = parts[2].lower()

                if category not in iDesignValidator.ALLOWED_CATEGORIES:
                    # Only enforce categorization for source code
                    if p.suffix in {".py", ".ts", ".js"}:
                        violations.append(iDesignViolation(
                            code=ViolationCode.CATEGORY_VIOLATION,
                            severity="error",
                            message=f"Unrecognized component category '{category}'. Source code must be in an allowed category.",
                            path=path_str
                        ))
                    continue # No need to check naming if category is invalid or it's a non-code file

                # --- NAMING CONVENTION ENFORCEMENT ---
                filename = p.name.lower()
                if category == "managers" and "manager" not in filename:
                    violations.append(iDesignViolation(
                        code=ViolationCode.NAMING_VIOLATION,
                        severity="error",
                        message=f"Manager component '{path_str}' must include 'Manager' in the filename.",
                        path=path_str
                    ))
                
                if category == "engines" and "engine" not in filename:
                    violations.append(iDesignViolation(
                        code=ViolationCode.NAMING_VIOLATION,
                        severity="error",
                        message=f"Engine component '{path_str}' must include 'Engine' in the filename.",
                        path=path_str
                    ))
                
                if category == "accessors" and "accessor" not in filename:
                    violations.append(iDesignViolation(
                        code=ViolationCode.NAMING_VIOLATION,
                        severity="error",
                        message=f"Accessor component '{path_str}' must include 'Accessor' in the filename.",
                        path=path_str
                    ))
        
        return violations

