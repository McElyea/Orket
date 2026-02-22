# Orket Contract Package (Heavy Artifacts)

Status: Living contract package payload dump for modularize work.
Package version: `1.0.0-rc4-freeze`
Grand Seal (manifest SHA-256): `ca095ab58519509d22bae0605082e633c4dbc459a9df3b3261c2190ec410c9cc`
Authoritative stage order: `base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`

## 1) Artifact Inventory (`filename`, `$id`, purpose)

1. `reference.schema.json`
   `$id`: `https://orket.dev/schema/v1/reference.schema.json`
   Purpose: canonical reference object shape.
2. `links.schema.json`
   `$id`: `https://orket.dev/schema/v1/links.schema.json`
   Purpose: links container value-shape.
3. `invocation.links.schema.json`
   `$id`: `https://orket.dev/schema/v1/invocation.links.schema.json`
   Purpose: invocation links keyspace and containers.
4. `validation_result.links.schema.json`
   `$id`: `https://orket.dev/schema/v1/validation_result.links.schema.json`
   Purpose: validation_result links keyspace and containers.
5. `relationship-vocabulary.schema.json`
   `$id`: `https://orket.dev/schema/v1/relationship-vocabulary.schema.json`
   Purpose: schema for relationship vocabulary instance.
6. `relationship-vocabulary.json`
   `$id`: `https://orket.dev/schema/v1/relationship-vocabulary.json`
   Purpose: allowed relationships and cardinality.
7. `raw_id.policy.schema.json`
   `$id`: `https://orket.dev/schema/v1/raw_id.policy.schema.json`
   Purpose: schema for raw-id policy instance.
8. `raw_id.policy.json`
   `$id`: `https://orket.dev/schema/v1/raw_id.policy.json`
   Purpose: forbidden raw-id tokens and local exceptions.
9. `validation.errors.schema.json`
   `$id`: `https://orket.dev/schema/v1/validation.errors.schema.json`
   Purpose: schema for error registry instance.
10. `validation.errors.json`
    `$id`: `https://orket.dev/schema/v1/validation.errors.json`
    Purpose: canonical error code registry.
11. `links.determinism.schema.json`
    `$id`: `https://orket.dev/schema/v1/links.determinism.schema.json`
    Purpose: determinism manifest shape for DTO links arrays.
12. `invocation.links.determinism.json`
    `$id`: `https://orket.dev/schema/v1/invocation.links.determinism.json`
    Purpose: invocation array ordering policy.
13. `validation_result.links.determinism.json`
    `$id`: `https://orket.dev/schema/v1/validation_result.links.determinism.json`
    Purpose: validation_result array ordering policy.
14. `orket.references.package.json`
    `$id`: `https://orket.dev/schema/v1/orket.references.package.json`
    Purpose: package identity, stage order, and integrity root.

## 2) Final `orket.references.package.json` (hashed manifest body)

```json
{
  "$id": "https://orket.dev/schema/v1/orket.references.package.json",
  "package_name": "orket.references",
  "package_version": "1.0.0-rc4-freeze",
  "stage_order": [
    "base_shape",
    "dto_links",
    "relationship_vocabulary",
    "policy",
    "determinism"
  ],
  "integrity": {
    "encoding": "utf-8",
    "hash_algorithm": "sha256",
    "hash_scope": "artifact_bytes",
    "line_endings": "lf",
    "trailing_newline": "required"
  },
  "artifacts": {
    "reference_schema": {
      "url": "https://orket.dev/schema/v1/reference.schema.json",
      "sha256": "3733ac8c74da040deec5f3627029ed9af6fb71d5fba03be5b24e4007f9d50725"
    },
    "links_schema": {
      "url": "https://orket.dev/schema/v1/links.schema.json",
      "sha256": "c8c19f9ceefc1c0fbebc8f0ca0025536e7f1c3ed8cdc47059158792c8d3d5747"
    },
    "relationship_vocabulary": {
      "url": "https://orket.dev/schema/v1/relationship-vocabulary.json",
      "sha256": "ec783539684f8f4fd52652e36ad53c090bd6c9068b4e679807430124de91451d"
    },
    "raw_id_policy": {
      "url": "https://orket.dev/schema/v1/raw_id.policy.json",
      "sha256": "79ac8d8f40629c0df715b27dbd756b33bd12181a012cebd9e5445ed4dc850fc2"
    },
    "error_registry": {
      "url": "https://orket.dev/schema/v1/validation.errors.json",
      "sha256": "8b7c992fb90f12237d099d4a0abf69d18974f36a577d9e64a3a7e3c687e2b437"
    },
    "invocation_links_schema": {
      "url": "https://orket.dev/schema/v1/invocation.links.schema.json",
      "sha256": "4c94696ada6335d138832a465df1bd03b061bfd415fc3994d080894f390e4d1a"
    },
    "validation_result_links_schema": {
      "url": "https://orket.dev/schema/v1/validation_result.links.schema.json",
      "sha256": "bf66e194496c400c3d91b77e5215f346ce5f75bb41ae840a7fffb0340ec4992a"
    },
    "determinism_schema": {
      "url": "https://orket.dev/schema/v1/links.determinism.schema.json",
      "sha256": "77507bc219ddf1a80f641a31558bf73350c35ba33a7ada0ecdd433e48e4175e2"
    },
    "invocation_determinism": {
      "url": "https://orket.dev/schema/v1/invocation.links.determinism.json",
      "sha256": "83e9d3e1b0b4375d2654e910f57d4c7f9e501938762ed3f91fdda40fe5bd5502"
    },
    "validation_result_determinism": {
      "url": "https://orket.dev/schema/v1/validation_result.links.determinism.json",
      "sha256": "9888d093c0e39185f6570eb191a8bf6dcfaf5d081ee62050dd22cc3d815ec35b"
    }
  }
}
```

## 3) Final SHA-256 List (11 artifacts)

0. `orket.references.package.json` (Grand Seal)
   `ca095ab58519509d22bae0605082e633c4dbc459a9df3b3261c2190ec410c9cc`
1. `reference.schema.json`
   `3733ac8c74da040deec5f3627029ed9af6fb71d5fba03be5b24e4007f9d50725`
2. `links.schema.json`
   `c8c19f9ceefc1c0fbebc8f0ca0025536e7f1c3ed8cdc47059158792c8d3d5747`
3. `invocation.links.schema.json`
   `4c94696ada6335d138832a465df1bd03b061bfd415fc3994d080894f390e4d1a`
4. `validation_result.links.schema.json`
   `bf66e194496c400c3d91b77e5215f346ce5f75bb41ae840a7fffb0340ec4992a`
5. `relationship-vocabulary.json`
   `ec783539684f8f4fd52652e36ad53c090bd6c9068b4e679807430124de91451d`
6. `raw_id.policy.json`
   `79ac8d8f40629c0df715b27dbd756b33bd12181a012cebd9e5445ed4dc850fc2`
7. `validation.errors.json`
   `8b7c992fb90f12237d099d4a0abf69d18974f36a577d9e64a3a7e3c687e2b437`
8. `links.determinism.schema.json`
   `77507bc219ddf1a80f641a31558bf73350c35ba33a7ada0ecdd433e48e4175e2`
9. `invocation.links.determinism.json`
   `83e9d3e1b0b4375d2654e910f57d4c7f9e501938762ed3f91fdda40fe5bd5502`
10. `validation_result.links.determinism.json`
   `9888d093c0e39185f6570eb191a8bf6dcfaf5d081ee62050dd22cc3d815ec35b`

## 4) Relationship Vocabulary Schema + Instance

### 4.1 `relationship-vocabulary.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/relationship-vocabulary.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["relationships"],
  "properties": {
    "relationships": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["cardinality", "allowed_source_dto_types", "allowed_target_reference_types"],
        "properties": {
          "cardinality": { "enum": ["one", "many"] },
          "allowed_source_dto_types": {
            "type": "array",
            "items": { "enum": ["invocation", "validation_result"] }
          },
          "allowed_target_reference_types": {
            "type": "array",
            "items": { "type": "string" }
          }
        }
      }
    }
  }
}
```

### 4.2 `relationship-vocabulary.json`

```json
{
  "$id": "https://orket.dev/schema/v1/relationship-vocabulary.json",
  "relationships": {
    "declares": {
      "cardinality": "one",
      "allowed_source_dto_types": ["invocation", "validation_result"],
      "allowed_target_reference_types": ["skill", "entrypoint", "tool_profile"]
    },
    "derives_from": {
      "cardinality": "many",
      "allowed_source_dto_types": ["validation_result"],
      "allowed_target_reference_types": ["artifact"]
    },
    "validates": {
      "cardinality": "one",
      "allowed_source_dto_types": ["validation_result"],
      "allowed_target_reference_types": ["invocation"]
    },
    "produces": {
      "cardinality": "many",
      "allowed_source_dto_types": ["invocation", "validation_result"],
      "allowed_target_reference_types": ["trace_event"]
    },
    "causes": {
      "cardinality": "many",
      "allowed_source_dto_types": ["invocation", "validation_result"],
      "allowed_target_reference_types": ["trace_event", "artifact"]
    }
  }
}
```

## 5) Raw-ID Policy Schema + Instance

### 5.1 `raw_id.policy.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/raw_id.policy.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["forbidden_tokens", "allowed_local_ids"],
  "properties": {
    "allowed_local_ids": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "uniqueItems": true
    },
    "forbidden_tokens": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 },
      "uniqueItems": true
    }
  }
}
```

### 5.2 `raw_id.policy.json`

```json
{
  "$id": "https://orket.dev/schema/v1/raw_id.policy.json",
  "allowed_local_ids": [],
  "forbidden_tokens": [
    "skill_id",
    "entrypoint_id",
    "validation_result_id",
    "invocation_id",
    "artifact_id",
    "trace_event_id",
    "tool_profile_id",
    "workspace_id",
    "pending_gate_request_id"
  ]
}
```

## 6) Validation Error Registry Schema + Instance

### 6.1 `validation.errors.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/validation.errors.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["codes"],
  "properties": {
    "codes": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["stage", "description"],
        "properties": {
          "stage": {
            "enum": [
              "base_shape",
              "dto_links",
              "relationship_vocabulary",
              "policy",
              "determinism"
            ]
          },
          "description": { "type": "string" }
        }
      }
    }
  }
}
```

### 6.2 `validation.errors.json`

```json
{
  "$id": "https://orket.dev/schema/v1/validation.errors.json",
  "codes": {
    "E_BASE_SHAPE_INVALID_LINKS_VALUE": {
      "stage": "base_shape",
      "description": "Links value is not a valid object or reference shape."
    },
    "E_BASE_SHAPE_INVALID_REFERENCE": {
      "stage": "base_shape",
      "description": "Reference object failed structural schema."
    },
    "E_DTO_LINKS_UNKNOWN_KEY": {
      "stage": "dto_links",
      "description": "Unknown links key for the specified DTO type."
    },
    "E_DTO_LINKS_WRONG_CONTAINER_SHAPE": {
      "stage": "dto_links",
      "description": "Scalar/Array container mismatch for links key."
    },
    "E_TYPED_REF_MISMATCH": {
      "stage": "relationship_vocabulary",
      "description": "Reference type incompatible with its declared relationship."
    },
    "E_RELATIONSHIP_INCOMPATIBLE": {
      "stage": "relationship_vocabulary",
      "description": "Relationship triplet not permitted for this source/target pair."
    },
    "E_RELATIONSHIP_CARDINALITY_VIOLATION": {
      "stage": "relationship_vocabulary",
      "description": "Relationship cardinality (one) exceeded."
    },
    "E_POLICY_RAW_ID_FORBIDDEN": {
      "stage": "policy",
      "description": "Forbidden raw ID token detected in DTO keys."
    },
    "E_DETERMINISM_VIOLATION": {
      "stage": "determinism",
      "description": "Determinism manifest mismatch with DTO schema."
    }
  }
}
```

## 7) DTO Links Schemas

### 7.1 `invocation.links.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/invocation.links.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "InvocationLinks",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "skill": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "entrypoint": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "validation_result": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "trace_events": {
      "type": "array",
      "items": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" }
    }
  }
}
```

### 7.2 `validation_result.links.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/validation_result.links.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ValidationResultLinks",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "skill": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "entrypoint": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "tool_profile": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "invocation": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" },
    "artifacts": {
      "type": "array",
      "items": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" }
    },
    "trace_events": {
      "type": "array",
      "items": { "$ref": "https://orket.dev/schema/v1/reference.schema.json" }
    }
  }
}
```

## 8) Determinism Schema + Per-DTO Manifests

### 8.1 `links.determinism.schema.json`

```json
{
  "$id": "https://orket.dev/schema/v1/links.determinism.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "LinksDeterminism",
  "type": "object",
  "required": ["order_insensitive"],
  "additionalProperties": false,
  "properties": {
    "order_insensitive": {
      "type": "array",
      "uniqueItems": true,
      "items": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" }
    }
  }
}
```

### 8.2 `invocation.links.determinism.json`

```json
{
  "$id": "https://orket.dev/schema/v1/invocation.links.determinism.json",
  "$schema": "https://orket.dev/schema/v1/links.determinism.schema.json",
  "order_insensitive": []
}
```

### 8.3 `validation_result.links.determinism.json`

```json
{
  "$id": "https://orket.dev/schema/v1/validation_result.links.determinism.json",
  "$schema": "https://orket.dev/schema/v1/links.determinism.schema.json",
  "order_insensitive": ["artifacts", "trace_events"]
}
```
