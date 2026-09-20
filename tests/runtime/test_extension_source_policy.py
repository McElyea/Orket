"""Source policy contracts and real installation admission."""
import asyncio
import os

import pytest

from orket.extensions.manager import ExtensionManager
from orket.extensions.source_policy import evaluate_source_policy
from tests.runtime.test_extension_manager import _init_test_extension_repo


@pytest.mark.parametrize("source", ["https://operator@example.com:443/repo", "https://operator:fake@example.com/repo"])
@pytest.mark.unit
def test_source_policy_refuses_inline_http_credentials_without_echoing_them(source):
    with pytest.raises(ValueError, match="E_EXT_SOURCE_INLINE_CREDENTIALS_DENIED") as failure:
        evaluate_source_policy(source, {})
    assert source not in str(failure.value)


@pytest.mark.integration
def test_install_from_repo_enforce_mode_blocks_local_path(tmp_path, monkeypatch):
    repo = tmp_path / "ext_repo_enforce"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_SOURCE_LOCAL_PATH_DENIED"):
        asyncio.run(manager.install_from_repo(str(repo)))


@pytest.mark.integration
def test_install_from_repo_compat_mode_records_fallbacks(tmp_path, monkeypatch):
    repo = tmp_path / "ext_repo_compat"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "compat")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = asyncio.run(manager.install_from_repo(str(repo)))
    assert "EXT_LOCAL_PATH_COMPAT" in record.compat_fallbacks


@pytest.mark.unit
def test_source_policy_enforce_denies_unapproved_host(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_HOST_DENIED"):
        evaluate_source_policy("https://example.com/repo.git", dict(os.environ))


@pytest.mark.unit
def test_source_policy_enforce_denies_unapproved_protocol(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_PROTOCOL_DENIED"):
        evaluate_source_policy("http://github.com/repo.git", dict(os.environ))


@pytest.mark.unit
def test_source_policy_compat_records_host_and_protocol_fallbacks(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "compat")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    decision = evaluate_source_policy("http://example.com/repo.git", dict(os.environ))
    assert decision.security_mode == "compat"
    assert "EXT_PROTOCOL_COMPAT" in decision.compat_fallbacks
    assert "EXT_HOST_COMPAT" in decision.compat_fallbacks
