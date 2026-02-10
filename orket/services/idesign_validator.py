import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from orket.domain.execution import ExecutionTurn

class iDesignValidator:
    """
    Mechanical Enforcer for iDesign structural integrity.
    Verifies that files are being created in the correct component categories.
    """
    
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
        "services"
    }

    @staticmethod
    def validate_turn(turn: ExecutionTurn, workspace_root: Path) -> Optional[str]:
        """
        Scans tool calls in a turn for file creations and verifies their placement.
        Returns an error message if a violation is found, else None.
        """
        for call in turn.tool_calls:
            if call.tool == "write_file":
                path_str = call.args.get("path")
                if not path_str: continue
                
                # Normalize path relative to workspace
                p = Path(path_str)
                
                # Root level files are generally discouraged in iDesign unless they are specific entry points
                # For now, we enforce that files must be in an allowed category subdirectory
                # or a product-specific subdirectory that follows the pattern.
                
                parts = p.parts
                if not parts: continue
                
                # If it's a flat file in the root (no directory), it's a violation
                if len(parts) == 1:
                    # Allow standard project root files (README, main.py, etc.)
                    # but agents should be putting code in components.
                    if p.suffix in {".py", ".ts", ".js"}:
                        return f"iDesign Violation: Source file '{path_str}' created in root. Code must be encapsulated in a component directory (e.g. /managers, /engines)."
                
                # Check if the primary directory is an allowed category
                category = parts[0].lower()
                
                # Check for product/src nesting
                if category in {"product", "src"} and len(parts) > 1:
                    category = parts[1].lower()
                    if category == "product" and len(parts) > 2:
                        category = parts[2].lower()

                if category not in iDesignValidator.ALLOWED_CATEGORIES:
                     return f"iDesign Violation: Unrecognized component category '{category}'. Files should be organized into: {list(iDesignValidator.ALLOWED_CATEGORIES)}"

                # --- NAMING CONVENTION ENFORCEMENT ---
                filename = p.name.lower()
                if category == "managers" and "manager" not in filename:
                    return f"iDesign Violation: Manager component '{path_str}' must include 'Manager' in the filename."
                
                if category == "engines" and "engine" not in filename:
                    return f"iDesign Violation: Engine component '{path_str}' must include 'Engine' in the filename."
                
                if category == "accessors" and "accessor" not in filename:
                    # Accessors are often named after the resource, but iDesign prefers explicit naming.
                    # We'll make this a warning or just enforce it for consistency.
                    return f"iDesign Violation: Accessor component '{path_str}' must include 'Accessor' in the filename."
        
        return None
