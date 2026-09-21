"""Declared JSON resources remain readable and valid outside the checkout."""
import json
from importlib.resources import files

import pytest
from jsonschema.validators import validator_for

pytestmark = pytest.mark.integration


def package_json(name):
    return json.loads(files("orket").joinpath(name).read_bytes())


@pytest.mark.parametrize("name", ["permissions.json", "permissions.schema.json", "kernel/v1/odr/artifact.schema.json"])
def test_core_json_resource_is_available_and_valid(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "permissions.json").write_text("malformed caller impostor", encoding="utf-8")
    payload = package_json(name)
    assert isinstance(payload, dict)
    schema = package_json("permissions.schema.json") if name == "permissions.json" else payload
    validator = validator_for(schema)
    validator.check_schema(schema)
    if name == "permissions.json":
        validator(schema).validate(payload)
