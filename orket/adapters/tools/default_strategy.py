from __future__ import annotations

from typing import Any, Callable, Dict


def compose_default_tool_map(toolbox: Any) -> Dict[str, Callable]:
    return {
        "read_file": toolbox.fs.read_file,
        "write_file": toolbox.fs.write_file,
        "list_directory": toolbox.fs.list_directory,
        "image_analyze": toolbox.vision.image_analyze,
        "image_generate": toolbox.vision.image_generate,
        "create_issue": toolbox.cards.create_issue,
        "update_issue_status": toolbox.cards.update_issue_status,
        "add_issue_comment": toolbox.cards.add_issue_comment,
        "get_issue_context": toolbox.cards.get_issue_context,
        "nominate_card": toolbox.governance.nominate_card,
        "report_credits": toolbox.governance.report_credits,
        "refinement_proposal": toolbox.governance.refinement_proposal,
        "request_excuse": toolbox.governance.request_excuse,
        "archive_eval": toolbox.academy.archive_eval,
        "promote_prompt": toolbox.academy.promote_prompt,
        "reforger_inspect": toolbox.reforger.inspect,
        "reforger_run": toolbox.reforger.run,
    }
