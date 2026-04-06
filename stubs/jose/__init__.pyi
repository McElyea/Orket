from typing import Any, Mapping

class _JWTModule:
    def encode(self, claims: Mapping[str, Any], key: str, algorithm: str) -> str: ...

jwt: _JWTModule
