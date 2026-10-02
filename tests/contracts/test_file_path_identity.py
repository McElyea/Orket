"""Pure resolved-path identity contracts; UNC values are not live SMB proof."""
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from orket.adapters.storage.async_file_tools import resolved_path_identity

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("ordinary,extended", [
    ("C:/workspace/file.txt", "//?/C:/workspace/file.txt"),
    ("c:/WORKSPACE/File.txt", "//?/C:/workspace/file.txt"),
    ("//server/share/workspace/file.txt", "//?/UNC/server/share/workspace/file.txt"),
    ("//SERVER/Share/workspace/file.txt", "//?/UNC/server/share/workspace/file.txt"),
])
def test_windows_native_namespace_aliases_have_one_identity(ordinary, extended):
    original, native = PureWindowsPath(ordinary), PureWindowsPath(extended)
    assert resolved_path_identity(original) == native
    assert resolved_path_identity(native) == native
    assert len({resolved_path_identity(original), resolved_path_identity(native)}) == 1
    assert str(original) == str(PureWindowsPath(ordinary))


@pytest.mark.parametrize("path", [
    PurePosixPath("/workspace/file.txt"), PurePosixPath("/workspace/File.txt"),
    PureWindowsPath("relative/file.txt"), PureWindowsPath("C:relative.txt"),
    PureWindowsPath("//./C:/workspace/file.txt"), PureWindowsPath("//?/Volume{example}/file.txt"),
])
def test_identity_preserves_other_path_forms(path):
    assert resolved_path_identity(path) is path


@pytest.mark.parametrize("target,root", [
    ("//?/C:/workspace_sibling/file.txt", "C:/workspace"),
    ("D:/workspace/file.txt", "//?/C:/workspace"),
    ("//other/share/workspace/file.txt", "//?/UNC/server/share/workspace"),
    ("//server/other/workspace/file.txt", "//?/UNC/server/share/workspace"),
    ("//./C:/workspace/file.txt", "C:/workspace"),
])
def test_identity_keeps_distinct_roots_outside_containment(target, root):
    assert not resolved_path_identity(PureWindowsPath(target)).is_relative_to(
        resolved_path_identity(PureWindowsPath(root)))


def test_posix_identity_preserves_case_sensitive_containment():
    assert not resolved_path_identity(PurePosixPath("/Workspace/file.txt")).is_relative_to(
        resolved_path_identity(PurePosixPath("/workspace")))
