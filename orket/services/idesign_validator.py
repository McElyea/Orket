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
                if category not in iDesignValidator.ALLOWED_CATEGORIES:
                    # Special case: products/sub-projects might have their own internal structure
                    if category == "product" or category == "src":
                        # If it's src/ or product/, check the next level
                        if len(parts) > 2:
                            sub_cat = parts[1].lower()
                            # If it's product/name/category, check the 3rd part
                            if category == "product" and len(parts) > 3:
                                sub_cat = parts[2].lower()
                                
                            if sub_cat not in iDesignValidator.ALLOWED_CATEGORIES:
                                return f"iDesign Violation: '{path_str}' is in an unrecognized component category '{sub_cat}'. Allowed: {list(iDesignValidator.ALLOWED_CATEGORIES)}"
                        else:
                            return f"iDesign Violation: '{path_str}' must be placed within a component subdirectory."
                    else:
                        return f"iDesign Violation: Unrecognized component category '{category}'. Files should be organized into: {list(iDesignValidator.ALLOWED_CATEGORIES)}"
        
        return None
