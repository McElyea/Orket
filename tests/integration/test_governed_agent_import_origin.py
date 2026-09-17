"""Exercise the real import wrapper in an isolated Python process."""

import asyncio
import sys
from pathlib import Path

import orket
from orket.extensions.governed_agent_process import sanitized_agent_environment

_DRIVER = '''
import builtins
import importlib
import sys
import threading
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from orket.extensions.sdk_workload_subprocess import (
    DeclaredStdlibImportHook, _guarded_import, _guarded_import_module,
)
root = Path(sys.argv[2])
hook = DeclaredStdlibImportHook(extension_root=root, allowed_stdlib_modules={'json'})
original_import, original_module = builtins.__import__, importlib.import_module
sys.path.insert(0, str(root))
try:
    builtins.__import__ = _guarded_import(hook, original_import)
    importlib.import_module = _guarded_import_module(hook, original_module)
    probe = importlib.import_module('origin_probe')
    assert probe.load('json').__name__ == 'json'
    failures = []
    def deny():
        for name, code in [('subprocess', 'E_EXT_STDLIB_IMPORT_UNDECLARED'), ('orket', 'E_EXT_IMPORT_BLOCKED')]:
            try:
                probe.load(name)
            except ImportError as exc:
                assert code in str(exc)
                failures.append(name)
            else:
                raise AssertionError('guard admitted ' + name)
    deny()
    hook._origin_inspection.active = True
    worker = threading.Thread(target=deny)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    hook._origin_inspection.active = False
    deny()
    assert failures == ['subprocess', 'orket'] * 3
    assert hook._origin_inspection.active is False
finally:
    builtins.__import__, importlib.import_module = original_import, original_module
print('origin_checks_passed')
'''


# Layer: integration
async def test_import_origin_inspection_does_not_recurse_or_bypass_other_threads(tmp_path: Path) -> None:
    # The child imports the same runtime distribution as the parent; no source overlay in wheel acceptance.
    extension = tmp_path / "extension"
    await asyncio.to_thread(extension.mkdir)
    await asyncio.to_thread((extension / "origin_probe.py").write_text,
                            "def load(name):\n    return __import__(name)\n", encoding="utf-8")
    driver = tmp_path / "driver.py"
    await asyncio.to_thread(driver.write_text, _DRIVER, encoding="utf-8")
    runtime_file = await asyncio.to_thread(Path(orket.__file__).resolve)
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(driver), str(runtime_file.parent.parent), str(extension),
        cwd=tmp_path, env=sanitized_agent_environment(),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == 0, stderr.decode()
    assert stdout.decode().strip() == "origin_checks_passed"
