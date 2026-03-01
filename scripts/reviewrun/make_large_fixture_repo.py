from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
import textwrap
import tempfile
import json
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

def baseline_files(repo: Path) -> None:
    # Small e-commerce-ish service with ordering / money logic
    write(repo / "app" / "__init__.py", "")
    write(repo / "app" / "config.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Settings:
            tax_rate: float = 0.0825
            free_shipping_threshold_cents: int = 5000
            enable_discount_stack: bool = False
            strict_currency_rounding: bool = True
    """))

    write(repo / "app" / "money.py", textwrap.dedent("""\
        # Money stored as integer cents.
        def round_cents(x: float) -> int:
            # Bankers rounding is NOT desired here; we want predictable round-half-up.
            return int(x + 0.5)

        def mul_cents(cents: int, rate: float) -> int:
            return round_cents(cents * rate)
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

        def shipping_cents(subtotal: int, free_threshold: int) -> int:
            return 0 if subtotal >= free_threshold else 799

        def total_cents(items: list[LineItem], tax_rate: float, free_threshold: int) -> int:
            sub = subtotal_cents(items)
            return sub + tax_cents(sub, tax_rate) + shipping_cents(sub, free_threshold)
    """))

    write(repo / "app" / "discounts.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Discount:
            code: str
            # percentage off, e.g. 0.10 for 10%
            percent: float

        def apply_percent(subtotal_cents: int, d: Discount) -> int:
            # deterministic, round-half-up handled by money.mul_cents in pricing layer
            return int(subtotal_cents * (1.0 - d.percent))
    """))

    write(repo / "app" / "orders.py", textwrap.dedent("""\
        from dataclasses import dataclass
        from .pricing import LineItem, total_cents
        from .config import Settings

        @dataclass(frozen=True)
        class Order:
            order_id: str
            items: list[LineItem]
            total: int

        def compute_order(order_id: str, items: list[LineItem], settings: Settings) -> Order:
            t = total_cents(items, settings.tax_rate, settings.free_shipping_threshold_cents)
            return Order(order_id=order_id, items=items, total=t)
    """))

    write(repo / "app" / "api.py", textwrap.dedent("""\
        import json
        from .pricing import LineItem
        from .orders import compute_order
        from .config import Settings

        def parse_items(payload: dict) -> list[LineItem]:
            items = []
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
            o = compute_order(order_id, items, Settings())
            return json.dumps({"order_id": o.order_id, "total_cents": o.total})
    """))

    # A small "sensitive ordering" registry table
    write(repo / "app" / "registry.py", textwrap.dedent("""\
        # Order of handlers is sensitive: first match wins.
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

    # Tests
    write(repo / "tests" / "test_pricing.py", textwrap.dedent("""\
        from app.pricing import LineItem, subtotal_cents, tax_cents, shipping_cents, total_cents
        from app.config import Settings

        def test_subtotal():
            items = [LineItem("a", 100, 2), LineItem("b", 250, 1)]
            assert subtotal_cents(items) == 450

        def test_total_basic():
            s = Settings()
            items = [LineItem("a", 1000, 1)]
            t = total_cents(items, s.tax_rate, s.free_shipping_threshold_cents)
            assert t >= 1000

        def test_shipping_threshold():
            s = Settings(free_shipping_threshold_cents=5000)
            assert shipping_cents(4999, s.free_shipping_threshold_cents) == 799
            assert shipping_cents(5000, s.free_shipping_threshold_cents) == 0
    """))

    write(repo / "tests" / "test_registry.py", textwrap.dedent("""\
        from app.registry import resolve_handler

        def test_resolve_handler():
            assert resolve_handler("PROMO10") == "percent"
            assert resolve_handler("FREESHIP") == "shipping"
            assert resolve_handler("missing") is None
    """))

    write(repo / "README.md", "Fixture repo for Orket ReviewRun stress tests.\n")

def messy_pr_changes(repo: Path) -> None:
    # A realistic “big” PR: refactor, new modules, subtle bugs, ordering changes,
    # config drift, and tests that don't catch the subtle parts.

    # config drift: add new settings and change default rounding policy (subtle)
    write(repo / "app" / "config.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Settings:
            tax_rate: float = 0.0825
            free_shipping_threshold_cents: int = 5000

            # New controls
            enable_discount_stack: bool = True
            strict_currency_rounding: bool = False  # NOTE: changed default (subtle)
            enable_promo_registry_v2: bool = True
            shipping_flat_cents: int = 799
    """))

    # money rounding changed: now uses int() truncation bug in one path
    write(repo / "app" / "money.py", textwrap.dedent("""\
        # Money stored as integer cents.
        # NOTE: new rounding behavior behind config in callers; keep helpers simple.

        def round_cents_half_up(x: float) -> int:
            return int(x + 0.5)

        def round_cents_trunc(x: float) -> int:
            # Subtle: truncation differs for .5 cases.
            return int(x)

        def mul_cents(cents: int, rate: float, *, strict: bool) -> int:
            raw = cents * rate
            return round_cents_half_up(raw) if strict else round_cents_trunc(raw)
    """))

    # pricing now includes discounts and “stacking”; introduces subtle shipping bug
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
            # Subtle bug: compares after-discounts instead of before-discounts.
            return 0 if subtotal_after_discounts >= free_threshold else shipping_flat

        def total_cents(
            items: list[LineItem],
            tax_rate: float,
            free_threshold: int,
            shipping_flat: int,
            discounts: list[Discount] | None,
            *,
            strict_rounding: bool,
            enable_stack: bool
        ) -> int:
            sub = subtotal_cents(items)
            sub_after = apply_discounts(sub, discounts or [], enable_stack=enable_stack)
            return sub_after + tax_cents(sub_after, tax_rate, strict_rounding=strict_rounding) + shipping_cents(sub_after, free_threshold, shipping_flat)
    """))

    # discounts expanded: ordering-sensitive stacking and new BOGO-type placeholder
    write(repo / "app" / "discounts.py", textwrap.dedent("""\
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Discount:
            code: str
            percent: float  # 0.10 => 10%

        def apply_percent(subtotal_cents: int, d: Discount) -> int:
            return int(subtotal_cents * (1.0 - d.percent))

        def apply_discounts(subtotal_cents: int, discounts: list[Discount], *, enable_stack: bool) -> int:
            if not discounts:
                return subtotal_cents

            # Ordering is sensitive: current code applies in input order.
            # Subtle: when enable_stack is False, only first discount is applied.
            if not enable_stack:
                return apply_percent(subtotal_cents, discounts[0])

            cur = subtotal_cents
            for d in discounts:
                cur = apply_percent(cur, d)
            return cur
    """))

    # registry ordering changed (sensitive): VIP moved ahead of PROMO10
    write(repo / "app" / "registry.py", textwrap.dedent("""\
        # Order of handlers is sensitive: first match wins.
        # v2: VIP should override others (per new business request)
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

    # orders now accepts discounts; adds “business logic” change; potential policy/regression point
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
            total: int

        def compute_order(order_id: str, items: list[LineItem], discounts: list[Discount] | None, settings: Settings) -> Order:
            ds = discounts or []
            t = total_cents(
                items,
                settings.tax_rate,
                settings.free_shipping_threshold_cents,
                settings.shipping_flat_cents,
                ds,
                strict_rounding=settings.strict_currency_rounding,
                enable_stack=settings.enable_discount_stack,
            )
            return Order(order_id=order_id, items=items, discounts=ds, total=t)
    """))

    # api changed: accepts discounts, parses codes, but no validation of percent ranges (subtle)
    write(repo / "app" / "api.py", textwrap.dedent("""\
        import json
        from .pricing import LineItem
        from .orders import compute_order
        from .discounts import Discount
        from .config import Settings
        from .registry import resolve_handler

        def parse_items(payload: dict) -> list[LineItem]:
            items = []
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
                    # Subtle: accepts percent like 25 (meaning 2500% off) if caller sends bad input.
                    out.append(Discount(code=code, percent=float(raw.get("percent", 0.0))))
            return out

        def handle_quote(body: str) -> str:
            payload = json.loads(body)
            order_id = payload.get("order_id", "unknown")
            items = parse_items(payload)
            discounts = parse_discounts(payload)
            o = compute_order(order_id, items, discounts, Settings())
            return json.dumps({"order_id": o.order_id, "total_cents": o.total, "discounts": [d.code for d in o.discounts]})
    """))

    # Add a “big” docs/config change
    write(repo / "README.md", textwrap.dedent("""\
        Fixture repo for Orket ReviewRun stress tests.

        Changes in this PR:
        - Added discount support to quote endpoint.
        - Registry v2 ordering changes (VIP prioritized).
        - Rounding behavior now configurable (default changed).
        - Shipping threshold now computed after discounts.

        NOTE: This repo is intentionally "review-hard".
    """))

    # Expand tests but miss subtle shipping/rounding edges
    write(repo / "tests" / "test_pricing.py", textwrap.dedent("""\
        from app.pricing import LineItem, subtotal_cents, total_cents
        from app.config import Settings
        from app.discounts import Discount

        def test_subtotal():
            items = [LineItem("a", 100, 2), LineItem("b", 250, 1)]
            assert subtotal_cents(items) == 450

        def test_total_with_discount_smoke():
            s = Settings()
            items = [LineItem("a", 1000, 1)]
            ds = [Discount("PROMO10", 0.10)]
            t = total_cents(items, s.tax_rate, s.free_shipping_threshold_cents, s.shipping_flat_cents, ds,
                            strict_rounding=s.strict_currency_rounding, enable_stack=s.enable_discount_stack)
            assert t > 0

        def test_discount_stack_order_smoke():
            s = Settings(enable_discount_stack=True)
            items = [LineItem("a", 1000, 1)]
            ds = [Discount("PROMO10", 0.10), Discount("VIP", 0.20)]
            t = total_cents(items, s.tax_rate, s.free_shipping_threshold_cents, s.shipping_flat_cents, ds,
                            strict_rounding=True, enable_stack=True)
            assert t > 0
    """))

    write(repo / "tests" / "test_registry.py", textwrap.dedent("""\
        from app.registry import resolve_handler

        def test_resolve_handler():
            assert resolve_handler("PROMO10") == "percent"
            assert resolve_handler("VIP") == "percent"
            assert resolve_handler("FREESHIP") == "shipping"
            assert resolve_handler("missing") is None
    """))

    # Add a new test file for API parsing but omit percent validation tests
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

def make_repo(seed: int = 1337) -> RepoInfo:
    random.seed(seed)
    tmp = Path(tempfile.mkdtemp(prefix="orket_reviewrun_large_fixture_"))
    repo = tmp / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    git_init(repo)
    baseline_files(repo)
    base = git_add_commit(repo, "baseline")

    messy_pr_changes(repo)
    head = git_add_commit(repo, "messy_pr_changes")

    return RepoInfo(repo_dir=repo, base_ref=base, head_ref=head)

if __name__ == "__main__":
    info = make_repo()
    print(json.dumps({
        "repo_dir": str(info.repo_dir),
        "base_ref": info.base_ref,
        "head_ref": info.head_ref,
    }, indent=2))
    print()
    print("Run:")
    print(f"  orket review diff --repo-root \"{info.repo_dir}\" --base {info.base_ref} --head {info.head_ref}")