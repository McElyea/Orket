"""Native child used to observe a canonical turn owner before process termination."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from tests.integration.test_turn_execution_ownership import ObservedToolbox, executor
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role


class PausedAfterWrite(ObservedToolbox):
    async def execute(self, tool_name, args, context=None):
        await super().execute(tool_name, args, context)
        await self.files.write_file("child-ready.txt", "effect retained; result unpublished")
        await asyncio.Event().wait()


async def main():
    workspace, db = Path(sys.argv[1]), Path(sys.argv[2])
    await executor(workspace, db).execute_turn(_issue(), _role(), _Model(),
        PausedAfterWrite(workspace, "first"), _context(protocol_governed_enabled=sys.argv[3] == "protocol"))


if __name__ == "__main__":
    asyncio.run(main())
