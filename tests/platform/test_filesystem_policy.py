import pytest
from pathlib import Path

from orket.policy import FilesystemPolicy, create_session_policy


@pytest.fixture
def policy_paths(tmp_path):
    work_domain = tmp_path / "domain"
    workspace = work_domain / "workspace"
    reference = work_domain / "references"
    external = tmp_path / "external"

    workspace.mkdir(parents=True)
    reference.mkdir(parents=True)
    external.mkdir(parents=True)

    (workspace / "work.txt").write_text("w", encoding="utf-8")
    (reference / "ref.txt").write_text("r", encoding="utf-8")
    (work_domain / "domain.txt").write_text("d", encoding="utf-8")
    (external / "outside.txt").write_text("x", encoding="utf-8")

    policy = FilesystemPolicy(
        spaces={
            "work_domain": str(work_domain),
            "workspaces": [str(workspace)],
            "reference_spaces": [str(reference)],
        },
        policy={
            "read_scope": ["workspace", "reference", "domain"],
            "write_scope": ["workspace"],
        },
    )

    return {
        "work_domain": work_domain,
        "workspace": workspace,
        "reference": reference,
        "external": external,
        "policy": policy,
    }


@pytest.mark.parametrize(
    "path_key,expected",
    [
        ("workspace", True),
        ("reference", True),
        ("work_domain", True),
        ("external", False),
    ],
)
def test_can_read_by_scope(policy_paths, path_key, expected):
    p = policy_paths[path_key]
    if p.is_dir():
        candidate = p / "work.txt" if path_key == "workspace" else (
            p / "ref.txt" if path_key == "reference" else (
                p / "domain.txt" if path_key == "work_domain" else p / "outside.txt"
            )
        )
    else:
        candidate = p

    assert policy_paths["policy"].can_read(str(candidate)) is expected


@pytest.mark.parametrize(
    "path_key,expected",
    [
        ("workspace", True),
        ("reference", False),
        ("work_domain", False),
        ("external", False),
    ],
)
def test_can_write_by_scope(policy_paths, path_key, expected):
    p = policy_paths[path_key]
    candidate = p / "out.txt"
    assert policy_paths["policy"].can_write(str(candidate)) is expected


def test_launch_dir_is_readable():
    policy = create_session_policy(str(Path.cwd()))
    assert policy.can_read(str(Path.cwd())) is True


def test_launch_dir_not_writable():
    policy = create_session_policy(str(Path.cwd()))
    assert policy.can_write(str(Path.cwd())) is False


def test_add_workspace_allows_new_write(policy_paths):
    policy = policy_paths["policy"]
    new_workspace = policy_paths["work_domain"] / "workspace2"
    new_workspace.mkdir()

    assert policy.can_write(str(new_workspace / "new.txt")) is False
    policy.add_workspace(str(new_workspace))
    assert policy.can_write(str(new_workspace / "new.txt")) is True


def test_add_workspace_is_idempotent(policy_paths):
    policy = policy_paths["policy"]
    original_len = len(policy.workspaces)
    existing = str(policy_paths["workspace"])

    policy.add_workspace(existing)
    policy.add_workspace(existing)

    assert len(policy.workspaces) == original_len


def test_create_session_policy_default_scopes(tmp_path):
    policy = create_session_policy(str(tmp_path / "workspace"), [str(tmp_path / "refs")])

    assert policy.read_scope == ["workspace", "reference", "domain"]
    assert policy.write_scope == ["workspace"]


def test_create_session_policy_reference_is_read_only(tmp_path):
    workspace = tmp_path / "workspace"
    refs = tmp_path / "refs"
    workspace.mkdir()
    refs.mkdir()

    policy = create_session_policy(str(workspace), [str(refs)])

    assert policy.can_read(str(refs / "doc.md")) is True
    assert policy.can_write(str(refs / "doc.md")) is False


def test_create_session_policy_workspace_writable(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = create_session_policy(str(workspace), [])

    assert policy.can_read(str(workspace / "a.txt")) is True
    assert policy.can_write(str(workspace / "a.txt")) is True


def test_create_session_policy_domain_readable_not_writable(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    policy = create_session_policy(str(workspace), [])

    domain_candidate = Path.cwd() / "README.md"
    assert policy.can_read(str(domain_candidate)) is True
    assert policy.can_write(str(domain_candidate)) is False


def test_policy_with_restricted_read_scope(tmp_path):
    work_domain = tmp_path / "domain"
    workspace = work_domain / "workspace"
    reference = work_domain / "references"
    workspace.mkdir(parents=True)
    reference.mkdir(parents=True)

    policy = FilesystemPolicy(
        spaces={
            "work_domain": str(work_domain),
            "workspaces": [str(workspace)],
            "reference_spaces": [str(reference)],
        },
        policy={
            "read_scope": ["workspace"],
            "write_scope": ["workspace"],
        },
    )

    assert policy.can_read(str(workspace / "ok.txt")) is True
    assert policy.can_read(str(reference / "nope.txt")) is False


def test_policy_with_domain_write_scope(tmp_path):
    work_domain = tmp_path / "domain"
    workspace = work_domain / "workspace"
    workspace.mkdir(parents=True)

    policy = FilesystemPolicy(
        spaces={
            "work_domain": str(work_domain),
            "workspaces": [str(workspace)],
            "reference_spaces": [],
        },
        policy={
            "read_scope": ["workspace", "domain"],
            "write_scope": ["workspace", "domain"],
        },
    )

    assert policy.can_write(str(work_domain / "domain-write.txt")) is True

