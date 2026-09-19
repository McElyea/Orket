"""Contract checks for explicit project vendor composition and refusal."""
from pathlib import Path

import pytest

from orket.application.services.project_vendor_factory import create_project_vendor

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["ado", "jira", "unknown", "", None, 7])
async def test_unsupported_vendor_cannot_fall_back_to_local(kind, tmp_path):
    with pytest.raises(ValueError, match="E_VENDOR_UNSUPPORTED"):
        await create_project_vendor(settings={"vendor_type": kind}, project_root=tmp_path, runtime_db=tmp_path / "cards.db")


@pytest.mark.parametrize("root,database", [(None, None), (Path("relative"), None), (None, Path("cards.db"))])
async def test_local_vendor_requires_explicit_absolute_locations(root, database):
    with pytest.raises(ValueError, match="E_VENDOR_LOCAL_LOCATIONS_REQUIRED"):
        await create_project_vendor(settings={}, project_root=root, runtime_db=database)


async def test_project_root_cannot_be_relative(tmp_path):
    with pytest.raises(ValueError, match="E_VENDOR_PROJECT_ROOT_ABSOLUTE_REQUIRED"):
        await create_project_vendor(settings={}, project_root=Path("relative"), runtime_db=tmp_path / "cards.db")


@pytest.mark.parametrize("department", ["../other", "/absolute", "C:\\outside", "", None])
async def test_department_is_a_catalog_component(tmp_path, department):
    with pytest.raises(ValueError, match="E_VENDOR_CATALOG_COMPONENT_INVALID"):
        await create_project_vendor(settings={"active_department": department}, project_root=tmp_path, runtime_db=tmp_path / "cards.db")


@pytest.mark.parametrize("config", [None, {}, {"url": "https://example.invalid"}])
async def test_incomplete_gitea_configuration_is_refused(config):
    with pytest.raises(ValueError, match="E_VENDOR_GITEA_CONFIGURATION_REQUIRED"):
        await create_project_vendor(settings={"vendor_type": "gitea", "gitea_config": config})


@pytest.mark.parametrize("url", ["file:///local", "https://user:secret@example.invalid", "https://example.invalid?q=1", "https://example.invalid:0"])
async def test_gitea_base_url_cannot_embed_credentials_or_non_http_authority(url):
    with pytest.raises(ValueError, match="E_VENDOR_GITEA_URL_INVALID") as observed:
        await create_project_vendor(settings={"vendor_type": "gitea", "gitea_config": {
            "url": url, "token": "fixture-token", "owner": "owner", "repo": "repo",
        }})
    assert "secret" not in str(observed.value) and "fixture-token" not in str(observed.value)


@pytest.mark.parametrize("key,value", [("owner", "../other"), ("repo", "repo?query=1"), ("repo", ".")])
async def test_gitea_repository_is_an_explicit_path_component(key, value):
    config = {"url": "https://example.invalid", "token": "fixture-token", "owner": "owner", "repo": "repo", key: value}
    with pytest.raises(ValueError, match="E_VENDOR_GITEA_REPOSITORY_INVALID"):
        await create_project_vendor(settings={"vendor_type": "gitea", "gitea_config": config})
