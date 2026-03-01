# ExtensionManager Decomposition Map

Source: `orket/extensions/manager.py`
Size: 822 lines (925 with imports/inner class), 31 methods + 1 inner class
Production importers: interfaces/api.py, interfaces/cli.py
Test importers: 5 test files
Script importers: 6 scripts

## Instance State (3 variables)

```
self.catalog_path: Path    # Path to extensions_catalog.json
self.project_root: Path    # Workspace root
self.install_root: Path    # ~/.orket/extensions
```

## Public API (preserve as-is)

- `ExtensionManager(catalog_path, project_root)` -- constructor
- `ExtensionManager.list_extensions()` -- discovery
- `ExtensionManager.install_from_repo(repo_url, name)` -- installation
- `ExtensionManager.run_workload(extension_id, workload_id, input_config, workspace)` -- execution
- `ExtensionManager.resolve_workload(workload_id)` -- lookup

## Complete Method Inventory

### Group A: Discovery & Catalog -> ExtensionCatalog
| Lines | Method | Notes |
|---|---|---|
| 109-160 | `list_extensions()` | Load catalog + entry_points |
| 162-170 | `resolve_workload()` | Find workload by ID |
| 439-448 | `_load_catalog_payload()` | Read JSON with error handling |
| 450-452 | `_save_catalog_payload()` | Write JSON |
| 576-597 | `_row_from_record()` | Serialize ExtensionRecord to dict |
| 902-924 | `_discover_entry_point_rows()` | Python entry_points loading |

### Group B: Manifest Parsing -> ManifestParser
| Lines | Method | Notes |
|---|---|---|
| 454-478 | `_load_manifest()` | Detect format (legacy JSON vs SDK YAML) |
| 480-491 | `_record_from_manifest()` | Dispatch to legacy or SDK |
| 493-532 | `_legacy_record_from_manifest()` | Parse legacy orket_extension.json |
| 534-574 | `_sdk_record_from_manifest()` | Parse SDK manifest YAML/JSON |

### Group C: Installation (stays on coordinator)
| Lines | Method | Notes |
|---|---|---|
| 172-201 | `install_from_repo()` | Git clone + manifest load + catalog update |

### Group D: Workload Execution -> WorkloadExecutor
| Lines | Method | Notes |
|---|---|---|
| 203-232 | `run_workload()` | Dispatch: legacy vs SDK |
| 234-334 | `_run_legacy_workload()` | Full legacy pipeline |
| 336-437 | `_run_sdk_workload()` | Full SDK pipeline |
| 796-803 | `_run_validators()` | Post-run validation |
| 895-900 | `_run_command()` | Subprocess execution |

### Group E: Workload Loading -> WorkloadExecutor (sub-methods)
| Lines | Method | Notes |
|---|---|---|
| 599-628 | `_load_legacy_workload()` | Import module, call register() |
| 630-672 | `_load_sdk_workload()` | Import SDK entrypoint |
| 674-679 | `_parse_sdk_entrypoint()` | Parse "module:attr" format |
| 681-718 | `_validate_extension_imports()` | AST scan for blocked imports |

### Group F: Artifact & Capability -> WorkloadExecutor (sub-methods)
| Lines | Method | Notes |
|---|---|---|
| 720-733 | `_build_sdk_capability_registry()` | Build CapabilityRegistry |
| 735-748 | `_validate_sdk_artifacts()` | Verify path containment + digests |
| 750-760 | `_artifact_root()` | Compute artifact path |
| 882-893 | `_build_artifact_manifest()` | Walk files, compute digests |

### Group G: Reproducibility -> ReproducibilityEnforcer
| Lines | Method | Notes |
|---|---|---|
| 762-764 | `_reliable_mode_enabled()` | Env check |
| 766-778 | `_validate_required_materials()` | Input file validation |
| 780-794 | `_validate_clean_git_if_required()` | Git state enforcement |

### Group H: Provenance -> WorkloadExecutor (sub-methods)
| Lines | Method | Notes |
|---|---|---|
| 805-842 | `_build_provenance()` | Legacy execution record |
| 844-880 | `_build_sdk_provenance()` | SDK execution record |

### Inner Class: _WorkloadRegistry (lines 88-99)
Small (12 lines). Stays as-is.

## Dependency Graph

```
list_extensions()
  |-- ExtensionCatalog._load_catalog_payload()
  |-- ExtensionCatalog._discover_entry_point_rows()

install_from_repo()
  |-- ManifestParser._load_manifest()
  |-- ManifestParser._record_from_manifest()
  |-- ExtensionCatalog._load_catalog_payload()
  |-- ExtensionCatalog._save_catalog_payload()
  |-- ExtensionCatalog._row_from_record()

run_workload()
  |-- ExtensionCatalog.resolve_workload()     [for lookup]
  |-- WorkloadExecutor._run_legacy_workload()
  |   |-- WorkloadExecutor._load_legacy_workload()
  |   |   |-- WorkloadExecutor._validate_extension_imports()
  |   |-- WorkloadExecutor._artifact_root()
  |   |-- ReproducibilityEnforcer._reliable_mode_enabled()
  |   |-- ReproducibilityEnforcer._validate_required_materials()
  |   |-- ReproducibilityEnforcer._validate_clean_git_if_required()
  |   |-- WorkloadExecutor._run_validators()
  |   |-- WorkloadExecutor._build_provenance()
  |   |-- WorkloadExecutor._build_artifact_manifest()
  |-- WorkloadExecutor._run_sdk_workload()
  |   |-- WorkloadExecutor._load_sdk_workload()
  |   |   |-- WorkloadExecutor._parse_sdk_entrypoint()
  |   |   |-- WorkloadExecutor._validate_extension_imports()
  |   |-- WorkloadExecutor._build_sdk_capability_registry()
  |   |-- WorkloadExecutor._validate_sdk_artifacts()
  |   |-- WorkloadExecutor._artifact_root()
  |   |-- WorkloadExecutor._build_sdk_provenance()
  |   |-- WorkloadExecutor._build_artifact_manifest()
```

## Target File Layout

```
orket/extensions/
  manager.py                    # ExtensionManager coordinator (<200 lines)
  catalog.py                    # ExtensionCatalog (~120 lines)
  manifest_parser.py            # ManifestParser (~120 lines)
  workload_executor.py          # WorkloadExecutor (~300 lines)
  reproducibility.py            # ReproducibilityEnforcer (~60 lines)
```

## Migration Strategy

1. Extract ExtensionCatalog first (pure I/O, no async, no side effects).
2. Extract ManifestParser (pure parsing, no side effects).
3. Extract ReproducibilityEnforcer (isolated validation).
4. Extract WorkloadExecutor (largest piece, depends on Catalog + Reproducibility).
5. Slim ExtensionManager to coordinator.
6. Add re-exports in manager.py for backwards compatibility.
