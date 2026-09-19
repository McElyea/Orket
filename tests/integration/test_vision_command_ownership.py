"""Real image file effects with controlled inference; not live model proof."""
import asyncio
import base64
import json
import threading
from types import SimpleNamespace

import pytest

from orket.adapters.tools.families.vision import VisionTools
from orket.application.services.toolbox import ToolBox
from orket.application.services.vision_service import VisionService
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1sAAAAASUVORK5CYII=')


class EncodedImage:
    def save(self, path):
        path.write_bytes(PNG)


async def test_vision_does_not_claim_an_image_when_encoder_writes_nothing(tmp_path):
    class EmptyEncoder:
        def save(self, *args, **kwargs):
            pass

    tool = VisionTools(tmp_path, [], model_id='fixture-unused')
    tool._image_pipeline = lambda prompt: SimpleNamespace(images=[EmptyEncoder()])
    result = await asyncio.to_thread(tool.image_generate, {'path': 'output.png', 'prompt': 'red'})
    assert result['ok'] is False, result
    assert not await asyncio.to_thread((tmp_path / 'output.png').exists)


async def test_toolbox_captures_selected_model_and_publishes_exact_encoder_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr('orket.application.services.toolbox.get_setting', lambda *args: 'selected-model')
    toolbox = ToolBox({}, str(tmp_path), [], db_path=str(tmp_path / 'runtime.db'))
    monkeypatch.setattr('orket.application.services.toolbox.get_setting', lambda *args: 'late-model')
    observed = []

    def load(adapter):
        observed.append(adapter.model_id)
        return lambda prompt: SimpleNamespace(images=[EncodedImage()])

    monkeypatch.setattr(VisionTools, '_load_pipeline', load)
    result = await toolbox.execute('image_generate', {'prompt': 'image', 'path': 'nested/output.png'})
    assert result['ok'] is True, result
    assert observed == ['selected-model']
    assert await asyncio.to_thread((tmp_path / 'nested/output.png').read_bytes) == PNG
    assert not await asyncio.to_thread(lambda: list((tmp_path / 'nested').glob('.vision-*')))


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_vision_retains_captured_command_and_native_owner_through_interruption(tmp_path, monkeypatch, stop):
    entered, release = threading.Event(), threading.Event()
    observed = []

    def generate(prompt):
        observed.append(prompt)
        entered.set()
        assert release.wait(15)
        return SimpleNamespace(images=[EncodedImage()])

    monkeypatch.setattr(VisionTools, '_load_pipeline', lambda adapter: generate)
    service = VisionService(tmp_path, (), 'controlled-model')
    args = {'prompt': 'captured', 'path': 'captured.png'}
    command = service.image_generate(args)
    request = asyncio.create_task(asyncio.wait_for(command, 0.05) if stop == 'timeout' else command)
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        responsiveness_start = asyncio.get_running_loop().time()
        await asyncio.sleep(0.01)
        assert asyncio.get_running_loop().time() - responsiveness_start < 0.5
        args.update(prompt='late', path='late.png')
        if stop == 'cancel':
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        probe = ('import asyncio,json; from pathlib import Path; '
                 'from orket.application.services.vision_service import VisionService; '
                 'print(json.dumps(asyncio.run(VisionService(Path.cwd(),(),"unused").image_generate('
                 '{"prompt":"competing","path":"other.png"}))))')
        code, output, error = await child(tmp_path, ['-c', probe])
        other = json.loads(output)
        assert code == 0 and other['ok'] is False and 'E_VISION_UNCERTAIN:owner_busy' in other['error'], error
        assert not request.done()
        release.set()
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
        assert isinstance(result, asyncio.CancelledError if stop == 'cancel' else TimeoutError)
        assert observed == ['captured'] and await asyncio.to_thread((tmp_path / 'captured.png').read_bytes) == PNG
        assert not await asyncio.to_thread((tmp_path / 'late.png').exists)
        assert (await service.image_generate({'prompt': 'retry', 'path': 'retry.png'}))['ok'] is True
        assert not await asyncio.to_thread(lambda: list(tmp_path.glob('.vision-*')))
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)


async def test_vision_readback_refusal_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(VisionTools, '_load_pipeline', lambda adapter: lambda prompt: SimpleNamespace(images=[EncodedImage()]))
    target = tmp_path / 'output.png'
    original = type(target).read_bytes

    def wrong(path):
        return b'wrong readback' if path == target else original(path)

    monkeypatch.setattr(type(target), 'read_bytes', wrong)
    result = await VisionService(tmp_path, (), 'controlled-model').image_generate({'prompt': 'image', 'path': 'output.png'})
    assert result == {'ok': False, 'error': 'E_VISION_IMAGE_UNVERIFIED'}
    assert await asyncio.to_thread(original, target) == PNG
    assert not await asyncio.to_thread(lambda: list(tmp_path.glob('.vision-*')))


async def test_vision_refuses_escape_before_inference(tmp_path, monkeypatch):
    def forbidden(adapter):
        pytest.fail('Escaped path reached inference')

    monkeypatch.setattr(VisionTools, '_load_pipeline', forbidden)
    result = await VisionService(tmp_path, (), 'unused').image_generate({'prompt': 'image', 'path': '../escape.png'})
    assert result['ok'] is False and 'denied' in result['error']
