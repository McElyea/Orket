def test_kernel_v1_scaffold_exists() -> None:
    import importlib

    module = importlib.import_module("orket.kernel.v1")
    assert module is not None

