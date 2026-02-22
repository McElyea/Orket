# Modularize Notes (Historical/Non-Normative)

## HISTORICAL: 6-stage pipeline variants

Previous draft content referenced a 6-stage pipeline including `typed_reference`.
That is not current living truth.

Current living truth is exactly:

`base_shape -> dto_links -> relationship_vocabulary -> policy -> determinism`

## HISTORICAL: stage naming drift

Previous drafts used variants like:

1. `rel_vocab` (alias)
2. `typed_reference` as a separate stage
3. `Stage 6` determinism wording

These are retained as historical context only.

## HISTORICAL: raw-id policy key naming drift

Older material alternated between:

1. `forbidden_cross_layer_suffixes`
2. `forbidden_tokens`

Current living contract uses `forbidden_tokens`.

## HISTORICAL: mixed schema references

Older determinism manifests sometimes used generic JSON Schema links instead of the Orket determinism schema URL.
Current living contract anchors determinism manifests to:

`https://orket.dev/schema/v1/links.determinism.schema.json`
