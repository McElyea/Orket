from __future__ import annotations


def _normalize_token(raw: str) -> str:
    return str(raw or "").strip()


def parse_provider_model_map(raw: str) -> list[dict[str, str]]:
    text = str(raw or "").strip()
    if not text:
        return []

    pairs: list[dict[str, str]] = []
    segments = [segment.strip() for segment in text.split(";") if segment.strip()]
    for segment in segments:
        if "=" not in segment:
            raise ValueError(f"missing '=' in segment '{segment}'")
        provider_raw, models_raw = segment.split("=", 1)
        provider = _normalize_token(provider_raw)
        if not provider:
            raise ValueError(f"empty provider in segment '{segment}'")
        model_tokens = [_normalize_token(token) for token in models_raw.split("|") if _normalize_token(token)]
        if not model_tokens:
            pairs.append({"provider": provider, "model": ""})
            continue
        for model in model_tokens:
            pairs.append({"provider": provider, "model": model})
    return _dedupe_pairs(pairs)


def _pairs_from_zip(providers: list[str], models: list[str]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for index, provider_raw in enumerate(providers):
        provider = _normalize_token(provider_raw)
        if not provider:
            continue
        model = _normalize_token(models[index] if index < len(models) else "")
        pairs.append({"provider": provider, "model": model})
    return _dedupe_pairs(pairs)


def _pairs_from_single_provider_multi_model(providers: list[str], models: list[str]) -> list[dict[str, str]]:
    if len(providers) != 1:
        return []
    provider = _normalize_token(providers[0])
    if not provider:
        return []
    model_tokens = [_normalize_token(token) for token in models if _normalize_token(token)]
    if len(model_tokens) <= 1:
        return []
    return _dedupe_pairs([{"provider": provider, "model": model} for model in model_tokens])


def _dedupe_pairs(pairs: list[dict[str, str]]) -> list[dict[str, str]]:
    ordered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in pairs:
        provider = _normalize_token(str(row.get("provider") or ""))
        model = _normalize_token(str(row.get("model") or ""))
        key = (provider, model)
        if not provider or key in seen:
            continue
        seen.add(key)
        ordered.append({"provider": provider, "model": model})
    return ordered


def expand_case_pairs(
    *,
    providers: list[str],
    models: list[str],
    provider_model_map: str = "",
) -> list[dict[str, str]]:
    explicit_pairs = parse_provider_model_map(provider_model_map)
    if explicit_pairs:
        return explicit_pairs

    single_provider_pairs = _pairs_from_single_provider_multi_model(providers, models)
    if single_provider_pairs:
        return single_provider_pairs

    return _pairs_from_zip(providers, models)
