"""Native child paused before or after a Gitea local closeout commit."""
import asyncio
import sys
from pathlib import Path

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.integration.test_gitea_terminal_transaction import _worker


async def main():
    root, boundary = Path(sys.argv[1]), sys.argv[2]
    worker, adapter, _db = _worker(root)
    files = AsyncFileTools(root)
    original_save = AsyncControlPlaneRecordRepository.save_resource_record
    original_release = adapter.release_or_fail

    async def pause():
        await files.write_file('closeout-ready.txt', boundary)
        await asyncio.Event().wait()

    async def save_resource(repository, *, record):
        result = await original_save(repository, record=record)
        if boundary == 'before-commit' and record.current_observed_state.startswith('lease_status:lease_released;'):
            await pause()
        return result

    async def release(*args, **kwargs):
        await original_release(*args, **kwargs)
        await files.write_file('remote-final-state.txt', kwargs['final_state'])

    async def work(_):
        await files.write_file('work-ready.txt', 'physical effect observed')
        while not await asyncio.to_thread((root/'allow-closeout.txt').exists):  # noqa: ASYNC110 - cross-process file barrier
            await asyncio.sleep(0.02)
        return {'ok': True}

    AsyncControlPlaneRecordRepository.save_resource_record = save_resource
    adapter.release_or_fail = release
    await worker.run_once(work_fn=work)
    await pause()


if __name__ == '__main__':
    asyncio.run(main())
