from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
import random


@dataclass
class RepoInfo:
    repo_dir: Path
    base_ref: str
    head_ref: str


def sh(cmd: list[str], cwd: Path) -> str:
    out = subprocess.check_output(cmd, cwd=str(cwd), stderr=subprocess.STDOUT)
    return out.decode("utf-8", errors="replace").strip()


def write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", newline="\n")


def git_init(repo: Path) -> None:
    sh(["git", "init"], repo)
    sh(["git", "config", "user.email", "fixture@example.com"], repo)
    sh(["git", "config", "user.name", "Orket Fixture"], repo)


def git_add_commit(repo: Path, msg: str) -> str:
    sh(["git", "add", "-A"], repo)
    sh(["git", "commit", "-m", msg], repo)
    return sh(["git", "rev-parse", "HEAD"], repo)


# ----------------------------
# Baseline: small service-like codebase
# ----------------------------
def baseline(repo: Path) -> None:
    write(repo / "README.md", "Joseph PR fixture for Orket ReviewRun.\n")

    write(repo / "app" / "__init__.py", "")

    write(repo / "app" / "config.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Settings:
            tax_rate: float = 0.0825
            free_shipping_threshold_cents: int = 5000
            shipping_flat_cents: int = 799
            strict_currency_rounding: bool = True
            enable_discount_stack: bool = False
            enable_cache: bool = True
            cache_ttl_seconds: int = 60
    """))

    write(repo / "app" / "money.py", textwrap.dedent("""\
        # cents stored as int
        def round_half_up(x: float) -> int:
            return int(x + 0.5)

        def mul_cents(cents: int, rate: float) -> int:
            return round_half_up(cents * rate)
    """))

    write(repo / "app" / "pricing.py", textwrap.dedent("""\
        from dataclasses import dataclass
        from .money import mul_cents

        @dataclass(frozen=True)
        class LineItem:
            sku: str
            unit_price_cents: int
            qty: int

        def subtotal_cents(items: list[LineItem]) -> int:
            return sum(i.unit_price_cents * i.qty for i in items)

        def tax_cents(subtotal: int, tax_rate: float) -> int:
            return mul_cents(subtotal, tax_rate)

        def shipping_cents(subtotal_before_discounts: int, free_threshold: int, shipping_flat: int) -> int:
            return 0 if subtotal_before_discounts >= free_threshold else shipping_flat

        def total_cents(items: list[LineItem], tax_rate: float, free_threshold: int, shipping_flat: int) -> int:
            sub = subtotal_cents(items)
            return sub + tax_cents(sub, tax_rate) + shipping_cents(sub, free_threshold, shipping_flat)
    """))

    write(repo / "app" / "discounts.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Discount:
            code: str
            percent: float  # 0.10 => 10%

        def apply_percent(subtotal_cents: int, d: Discount) -> int:
            # baseline intentionally simple
            return int(subtotal_cents * (1.0 - d.percent))
    """))

    write(repo / "app" / "registry.py", textwrap.dedent("""\
        # Ordering is sensitive: first match wins.
        HANDLERS = [
            ("PROMO10", "percent"),
            ("FREESHIP", "shipping"),
            ("VIP", "percent"),
        ]

        def resolve_handler(code: str) -> str | None:
            for c, t in HANDLERS:
                if c == code:
                    return t
            return None
    """))

    write(repo / "app" / "cache.py", textwrap.dedent("""\
        import time
        from dataclasses import dataclass

        @dataclass
        class CacheEntry:
            value: str
            expires_at: float

        class SimpleCache:
            def __init__(self):
                self._m: dict[str, CacheEntry] = {}

            def get(self, k: str) -> str | None:
                e = self._m.get(k)
                if not e:
                    return None
                if time.time() >= e.expires_at:
                    self._m.pop(k, None)
                    return None
                return e.value

            def set(self, k: str, v: str, ttl_seconds: int) -> None:
                self._m[k] = CacheEntry(value=v, expires_at=time.time() + ttl_seconds)
    """))

    write(repo / "app" / "orders.py", textwrap.dedent("""\
        from dataclasses import dataclass
        from .pricing import LineItem, total_cents
        from .config import Settings

        @dataclass(frozen=True)
        class Order:
            order_id: str
            items: list[LineItem]
            total_cents: int

        def compute_order(order_id: str, items: list[LineItem], settings: Settings) -> Order:
            t = total_cents(items, settings.tax_rate, settings.free_shipping_threshold_cents, settings.shipping_flat_cents)
            return Order(order_id=order_id, items=items, total_cents=t)
    """))

    write(repo / "app" / "api.py", textwrap.dedent("""\
        import json
        from .pricing import LineItem
        from .orders import compute_order
        from .config import Settings
        from .cache import SimpleCache

        _cache = SimpleCache()

        def parse_items(payload: dict) -> list[LineItem]:
            items: list[LineItem] = []
            for it in payload.get("items", []):
                items.append(LineItem(
                    sku=str(it["sku"]),
                    unit_price_cents=int(it["unit_price_cents"]),
                    qty=int(it["qty"]),
                ))
            return items

        def handle_quote(body: str) -> str:
            payload = json.loads(body)
            order_id = payload.get("order_id", "unknown")
            items = parse_items(payload)

            key = json.dumps({"items": [i.__dict__ for i in items], "order_id": order_id}, sort_keys=True)
            s = Settings()
            if s.enable_cache:
                cached = _cache.get(key)
                if cached is not None:
                    return cached

            o = compute_order(order_id, items, s)
            out = json.dumps({"order_id": o.order_id, "total_cents": o.total_cents})
            if s.enable_cache:
                _cache.set(key, out, s.cache_ttl_seconds)
            return out
    """))

    # small tests
    write(repo / "tests" / "test_pricing.py", textwrap.dedent("""\
        from app.pricing import LineItem, subtotal_cents, total_cents
        from app.config import Settings

        def test_subtotal():
            items = [LineItem("a", 100, 2), LineItem("b", 250, 1)]
            assert subtotal_cents(items) == 450

        def test_total_smoke():
            s = Settings()
            items = [LineItem("a", 1000, 1)]
            assert total_cents(items, s.tax_rate, s.free_shipping_threshold_cents, s.shipping_flat_cents) > 0
    """))

    write(repo / "tests" / "test_registry.py", textwrap.dedent("""\
        from app.registry import resolve_handler

        def test_registry():
            assert resolve_handler("VIP") == "percent"
            assert resolve_handler("FREESHIP") == "shipping"
            assert resolve_handler("missing") is None
    """))


# ----------------------------
# “Joseph PR”: large, messy changes across many files
# ----------------------------
def joseph_pr(repo: Path, seed: int = 1337) -> None:
    rnd = random.Random(seed)

    # 1) Config drift: defaults change, a “debug” switch sneaks in, rounding default flips
    write(repo / "app" / "config.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Settings:
            tax_rate: float = 0.0825
            free_shipping_threshold_cents: int = 5000
            shipping_flat_cents: int = 799

            # behavior defaults changed (subtle)
            strict_currency_rounding: bool = False  # was True
            enable_discount_stack: bool = True      # was False

            # new flags
            enable_cache: bool = True
            cache_ttl_seconds: int = 10             # was 60
            debug: bool = True                      # new, dangerous default
    """))

    # 2) Money: introduces truncation path and float pitfalls
    write(repo / "app" / "money.py", textwrap.dedent("""\
        def round_half_up(x: float) -> int:
            return int(x + 0.5)

        def round_trunc(x: float) -> int:
            # subtle: truncation differs around .5 and negative values
            return int(x)

        def mul_cents(cents: int, rate: float, *, strict: bool) -> int:
            raw = cents * rate
            return round_half_up(raw) if strict else round_trunc(raw)
    """))

    # 3) Discounts: stacking order-sensitive; accepts unbounded percent
    write(repo / "app" / "discounts.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Discount:
            code: str
            percent: float  # expected 0.0..1.0

        def apply_percent(subtotal_cents: int, d: Discount) -> int:
            return int(subtotal_cents * (1.0 - d.percent))

        def apply_discounts(subtotal_cents: int, discounts: list[Discount], *, enable_stack: bool) -> int:
            if not discounts:
                return subtotal_cents
            if not enable_stack:
                return apply_percent(subtotal_cents, discounts[0])

            cur = subtotal_cents
            # ordering is sensitive: applies in provided order (can regress totals)
            for d in discounts:
                cur = apply_percent(cur, d)
            return cur
    """))

    # 4) Registry ordering change (sensitive)
    write(repo / "app" / "registry.py", textwrap.dedent("""\
        # Ordering is sensitive: first match wins.
        # Joseph change: VIP moved first to "override" everything
        HANDLERS = [
            ("VIP", "percent"),
            ("PROMO10", "percent"),
            ("FREESHIP", "shipping"),
        ]

        def resolve_handler(code: str) -> str | None:
            for c, t in HANDLERS:
                if c == code:
                    return t
            return None
    """))

    # 5) Pricing: shipping threshold now computed after discounts (business logic change)
    write(repo / "app" / "pricing.py", textwrap.dedent("""\
        from dataclasses import dataclass
        from .money import mul_cents
        from .discounts import Discount, apply_discounts

        @dataclass(frozen=True)
        class LineItem:
            sku: str
            unit_price_cents: int
            qty: int

        def subtotal_cents(items: list[LineItem]) -> int:
            return sum(i.unit_price_cents * i.qty for i in items)

        def tax_cents(subtotal: int, tax_rate: float, *, strict_rounding: bool) -> int:
            return mul_cents(subtotal, tax_rate, strict=strict_rounding)

        def shipping_cents(subtotal_after_discounts: int, free_threshold: int, shipping_flat: int) -> int:
            # subtle: threshold applied AFTER discounts (may remove free shipping unexpectedly)
            return 0 if subtotal_after_discounts >= free_threshold else shipping_flat

        def total_cents(
            items: list[LineItem],
            tax_rate: float,
            free_threshold: int,
            shipping_flat: int,
            discounts: list[Discount],
            *,
            strict_rounding: bool,
            enable_stack: bool
        ) -> int:
            sub = subtotal_cents(items)
            sub_after = apply_discounts(sub, discounts, enable_stack=enable_stack)
            return sub_after + tax_cents(sub_after, tax_rate, strict_rounding=strict_rounding) + shipping_cents(sub_after, free_threshold, shipping_flat)
    """))

    # 6) Cache: adds concurrency bug via shared mutable state and “debug logging” leaks
    write(repo / "app" / "cache.py", textwrap.dedent("""\
        import time
        from dataclasses import dataclass

        @dataclass
        class CacheEntry:
            value: str
            expires_at: float

        class SimpleCache:
            def __init__(self):
                self._m: dict[str, CacheEntry] = {}
                self._hits = 0  # debug counter (not threadsafe)

            def get(self, k: str) -> str | None:
                self._hits += 1
                e = self._m.get(k)
                if not e:
                    return None
                if time.time() >= e.expires_at:
                    self._m.pop(k, None)
                    return None
                return e.value

            def set(self, k: str, v: str, ttl_seconds: int) -> None:
                self._m[k] = CacheEntry(value=v, expires_at=time.time() + ttl_seconds)

            def stats(self) -> dict:
                return {"hits": self._hits, "size": len(self._m)}
    """))

    # 7) API: parses discounts, accepts invalid percent, logs secrets-ish data when debug
    write(repo / "app" / "api.py", textwrap.dedent("""\
        import json
        from .pricing import LineItem
        from .orders import compute_order
        from .config import Settings
        from .discounts import Discount
        from .registry import resolve_handler
        from .cache import SimpleCache

        _cache = SimpleCache()

        def parse_items(payload: dict) -> list[LineItem]:
            items: list[LineItem] = []
            for it in payload.get("items", []):
                items.append(LineItem(
                    sku=str(it["sku"]),
                    unit_price_cents=int(it["unit_price_cents"]),
                    qty=int(it["qty"]),
                ))
            return items

        def parse_discounts(payload: dict) -> list[Discount]:
            out: list[Discount] = []
            for raw in payload.get("discounts", []):
                code = str(raw.get("code", ""))
                handler = resolve_handler(code)
                if handler == "percent":
                    # bug: accepts percent like 25 (2500% off)
                    out.append(Discount(code=code, percent=float(raw.get("percent", 0.0))))
            return out

        def handle_quote(body: str) -> str:
            payload = json.loads(body)
            order_id = payload.get("order_id", "unknown")
            items = parse_items(payload)
            discounts = parse_discounts(payload)

            key = json.dumps({"items": [i.__dict__ for i in items], "order_id": order_id, "discounts": [d.__dict__ for d in discounts]}, sort_keys=True)

            s = Settings()
            if s.debug:
                # dangerous: logs full request payload
                print("DEBUG payload=", payload)

            if s.enable_cache:
                cached = _cache.get(key)
                if cached is not None:
                    return cached

            o = compute_order(order_id, items, discounts, s)
            out = json.dumps({"order_id": o.order_id, "total_cents": o.total_cents, "discounts": [d.code for d in o.discounts]})
            if s.enable_cache:
                _cache.set(key, out, s.cache_ttl_seconds)
            return out
    """))

    # 8) Orders: now includes discounts, behavior change
    write(repo / "app" / "orders.py", textwrap.dedent("""\
        from dataclasses import dataclass
        from .pricing import LineItem, total_cents
        from .discounts import Discount
        from .config import Settings

        @dataclass(frozen=True)
        class Order:
            order_id: str
            items: list[LineItem]
            discounts: list[Discount]
            total_cents: int

        def compute_order(order_id: str, items: list[LineItem], discounts: list[Discount], settings: Settings) -> Order:
            t = total_cents(
                items,
                settings.tax_rate,
                settings.free_shipping_threshold_cents,
                settings.shipping_flat_cents,
                discounts,
                strict_rounding=settings.strict_currency_rounding,
                enable_stack=settings.enable_discount_stack,
            )
            return Order(order_id=order_id, items=items, discounts=discounts, total_cents=t)
    """))

    # 9) Add a bunch of “touched everywhere” modules to create 30+ pages
    #    These are mostly boilerplate but include subtle issues and TODO/FIXME noise.
    for i in range(1, 19):  # 18 extra modules
        name = f"feature_{i:02d}.py"
        lines = []
        lines.append("# generated feature module\n")
        if i % 4 == 0:
            lines.append("TODO: remove debug path\n")
        if i % 6 == 0:
            lines.append("FIXME: handle negative values correctly\n")
        # subtle: inconsistent return types
        lines.append("def compute(x: int):\n")
        if i % 5 == 0:
            lines.append("    return str(x + 1)\n")
        else:
            lines.append("    return x + 1\n")
        # a little “sensitive ordering” list
        lines.append("\nORDER = [\n")
        for j in range(10):
            # shuffle a little to create diff noise
            k = (j * 7 + i) % 10
            lines.append(f"    {k},\n")
        lines.append("]\n")
        write(repo / "app" / name, "".join(lines))

    # Tests: add more tests, but still miss the real edge cases
    write(repo / "tests" / "test_api.py", textwrap.dedent("""\
        import json
        from app.api import handle_quote

        def test_quote_smoke():
            body = json.dumps({
                "order_id": "o1",
                "items": [{"sku":"a","unit_price_cents":1000,"qty":1}],
                "discounts": [{"code":"PROMO10","percent":0.10}]
            })
            out = json.loads(handle_quote(body))
            assert out["order_id"] == "o1"
            assert out["total_cents"] > 0
    """))

    write(repo / "tests" / "test_pricing.py", textwrap.dedent("""\
        from app.pricing import LineItem, total_cents
        from app.config import Settings
        from app.discounts import Discount

        def test_total_smoke_with_discount():
            s = Settings()
            items = [LineItem("a", 1000, 1)]
            ds = [Discount("PROMO10", 0.10)]
            t = total_cents(items, s.tax_rate, s.free_shipping_threshold_cents, s.shipping_flat_cents, ds,
                            strict_rounding=s.strict_currency_rounding, enable_stack=s.enable_discount_stack)
            assert t > 0
    """))

    # README changes for noise
    write(repo / "README.md", textwrap.dedent("""\
        Joseph PR fixture for Orket ReviewRun.

        This fixture intentionally includes:
        - ordering-sensitive changes
        - config default drift
        - rounding behavior drift
        - discount parsing risks
        - debug logging in prod path
        - many touched files for "30 pages of diff"
    """))


def make_repo() -> RepoInfo:
    tmp = Path(tempfile.mkdtemp(prefix="orket_reviewrun_joseph_30page_"))
    repo = tmp / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    git_init(repo)

    baseline(repo)
    base = git_add_commit(repo, "baseline")

    joseph_pr(repo, seed=1337)
    head = git_add_commit(repo, "joseph_30page_pr")

    return RepoInfo(repo_dir=repo, base_ref=base, head_ref=head)


if __name__ == "__main__":
    info = make_repo()
    print(json.dumps({
        "repo_dir": str(info.repo_dir),
        "base_ref": info.base_ref,
        "head_ref": info.head_ref,
        "app_files": sorted([p.as_posix() for p in (info.repo_dir / "app").glob("*.py")]),
    }, indent=2))
    print()
    print("Run diff:")
    print(f'  orket review diff --repo-root "{info.repo_dir}" --base {info.base_ref} --head {info.head_ref} --json')
    print("Run files (app only):")
    print(f'  orket review files --repo-root "{info.repo_dir}" --ref {info.head_ref} --paths app/*.py --json')