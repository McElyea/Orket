"""Real public CLI/file/HTTP ownership with controlled model responses, not live model proof."""
import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from dotenv import dotenv_values

from orket.adapters.llm.llama_cpp_render_verification import QWEN38_TEXT_TEMPLATE_PATH, expected_text_render
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def catalog_server():
    state = {"model": DEFAULT_LOCAL_MODEL, "response": "42", "calls": []}
    template = QWEN38_TEXT_TEMPLATE_PATH.read_bytes().decode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Controlled local fixture; requests are retained below.

        def do_GET(self):
            state["calls"].append(self.path)
            if self.path == "/props":
                self.respond({"model_alias": DEFAULT_LOCAL_MODEL, "chat_template": template,
                              "default_generation_settings": {"n_ctx": 8192}})
                return
            self.respond({"data": [{"id": state["model"]}] if state["model"] else []})

        def do_POST(self):
            state["calls"].append(self.path)
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/apply-template":
                self.respond({"prompt": expected_text_render(json.loads(body)["messages"])})
                return
            if self.path == "/tokenize":
                self.respond({"tokens": list(range(10))})
                return
            state["request"] = json.loads(body)
            response = state["response"](state["request"]) if callable(state["response"]) else state["response"]
            self.respond({"model": DEFAULT_LOCAL_MODEL, "choices": [{"message": {"role": "assistant",
                         "content": response}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}})

        def respond(self, payload):
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


async def setup(root, endpoint, *, extra=()):
    project, models = root / "Project café with spaces", root / "gguf"
    await asyncio.to_thread(models.mkdir, exist_ok=True)
    # Inventory fixture only; these bytes are explicitly not a valid model.
    await asyncio.to_thread((models / f"{DEFAULT_LOCAL_MODEL}.gguf").write_bytes, b"controlled inventory fixture")
    args = ["-m", "orket.cli", "setup", "--project", str(project), "--non-interactive",
            "--provider", "llama_cpp", "--base-url", endpoint, "--model-id", DEFAULT_LOCAL_MODEL,
            "--gguf-root", str(models), *extra]
    code, output, error = await child(root, args)
    return project, code, output, error


async def test_setup_and_fresh_doctor_use_saved_project_provider(catalog_server, tmp_path):
    endpoint, state = catalog_server
    project, code, output, error = await setup(tmp_path, endpoint, extra=("--run-example", "--decision", "deny"))
    assert code == 0, output + error
    config = json.loads(await asyncio.to_thread((project / "config/organization.json").read_bytes))
    assert config["process_rules"]["default_llm"] == DEFAULT_LOCAL_MODEL
    env = await asyncio.to_thread(dotenv_values, project / ".env")
    assert env["ORKET_LLM_PROVIDER"] == "llama_cpp" and env["ORKET_LLM_LLAMA_CPP_BASE_URL"] == endpoint
    assert "mock model; no provider inference" in output
    assert not await asyncio.to_thread((project / "workspace/quickstart_out/hello_from_orket.txt").exists)
    code, output, error = await child(tmp_path, ["-m", "orket.cli", "doctor", "--project", str(project),
                                               "--inference", "--json"])
    assert code == 0, output + error
    report = json.loads(output)
    assert report["provider_observation"]["inference"] == "success"
    assert report["provider_observation"]["metal"] == "unverified"
    assert report["command_observation"]["cleanup_confirmed"]
    assert state["request"]["model"] == DEFAULT_LOCAL_MODEL and "/v1/chat/completions" in state["calls"]
    assert not await asyncio.to_thread((tmp_path / "config/organization.json").exists)


@pytest.mark.parametrize("failure", ["missing-model", "wrong-answer"])
async def test_diagnostics_do_not_convert_failed_admission_or_inference_to_success(catalog_server, tmp_path, failure):
    endpoint, state = catalog_server
    project, code, output, error = await setup(tmp_path, endpoint, extra=("--skip-check",))
    assert code == 0 and "not checked" in output, output + error
    state["model" if failure == "missing-model" else "response"] = "" if failure == "missing-model" else "43"
    code, output, error = await child(tmp_path, ["-m", "orket.cli", "doctor", "--project", str(project),
                                               "--inference", "--json"])
    assert code == 1, output + error
    report = json.loads(output)
    assert not report["ok"] and report["observed_result"] == "failure"
    assert report["provider"] == "llama_cpp"
    if failure == "missing-model":
        assert not report["provider_observation"]["catalog_admitted"]
        assert "/v1/chat/completions" not in state["calls"]
    else:
        assert report["provider_observation"]["inference"] == "failure"


async def test_missing_server_keeps_saved_files_but_fails_readiness(tmp_path):
    with socket.socket() as bound_without_listener:
        bound_without_listener.bind(("127.0.0.1", 0))
        endpoint = f"http://127.0.0.1:{bound_without_listener.getsockname()[1]}/v1"
        project, code, output, error = await setup(tmp_path, endpoint)
    assert code == 1 and "Model catalog admission: failed" in output, output + error
    assert "ModelConnectionError:" in output and "All connection attempts failed" in output, output + error
    assert "Inference: not_established" in output
    assert await asyncio.to_thread((project / ".env").is_file)


async def test_environment_publication_refuses_directory_after_explicit_partial_effects(tmp_path):
    project = tmp_path / "Project café with spaces"
    await asyncio.to_thread((project / ".env").mkdir, parents=True)
    _, code, output, error = await setup(tmp_path, "http://127.0.0.1:8080/v1", extra=("--skip-check",))
    assert code == 1 and "E_SETUP_ENVIRONMENT_NOT_REGULAR" in error, output + error
    assert "Initialization complete" not in output
    assert await asyncio.to_thread((project / "config/organization.json").is_file)


async def test_setup_preserves_unrelated_dotenv_entries_and_comments(tmp_path):
    project = tmp_path / "Project café with spaces"
    await asyncio.to_thread(project.mkdir)
    original = "# retain this comment\nUNRELATED='keep me'\nORKET_LLM_PROVIDER='ollama'\n"
    await asyncio.to_thread((project / ".env").write_text, original, encoding="utf-8")
    _, code, output, error = await setup(tmp_path, "http://127.0.0.1:8080/v1", extra=("--skip-check",))
    assert code == 0, output + error
    content = await asyncio.to_thread((project / ".env").read_text, encoding="utf-8")
    assert "# retain this comment" in content and content.count("ORKET_LLM_PROVIDER=") == 1
    values = await asyncio.to_thread(dotenv_values, project / ".env")
    assert values["UNRELATED"] == "keep me" and values["ORKET_LLM_PROVIDER"] == "llama_cpp"
