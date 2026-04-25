"""Woolies CLI - Woolworths NZ grocery management."""

import asyncio
import json
import math
import signal
import sys

import click

from . import __version__
from .banner import maybe_show_banner
from .browser import AuthError, BrowserSession
from .client import WoolworthsClient
from .config import ConfigError, load_credentials
from .paths import config_dir, config_file, state_dir

signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def _format_kg(value):
    """Format kilogram values without noisy trailing zeros."""
    if value is None:
        return None
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _format_currency(value):
    """Format numeric price values consistently."""
    if value is None:
        return None
    return f"${float(value):.2f}"


def _estimate_each_count(weight_value, average_weight_per_unit):
    """Convert stored weight back to an approximate item count."""
    if not weight_value or not average_weight_per_unit:
        return None

    estimated = float(weight_value) / float(average_weight_per_unit)
    rounded = round(estimated)
    if math.isclose(estimated, rounded, rel_tol=1e-9, abs_tol=1e-9):
        return rounded
    return estimated


def _format_dual_pricing(product):
    """Describe dual-priced loose produce for display."""
    details = ["Each or Kg"]

    average_price = product.get("average_price_per_each")
    average_weight = product.get("average_weight_per_unit")
    minimum_quantity = product.get("minimum_quantity")
    maximum_quantity = product.get("maximum_quantity")
    increment = product.get("quantity_increment")

    if average_price is not None:
        details.append(f"avg each {_format_currency(average_price)}")
    if average_weight is not None:
        details.append(f"avg wt {_format_kg(average_weight)}kg")
    if (
        minimum_quantity is not None
        and maximum_quantity is not None
        and increment is not None
    ):
        details.append(
            f"kg range {_format_kg(minimum_quantity)}-{_format_kg(maximum_quantity)} "
            f"(step {_format_kg(increment)})"
        )

    return " | ".join(details)


def _build_cart_line(product):
    """Render a cart quantity label that explains dual-priced produce."""
    quantity_data = product.get("quantity", {})
    stored_quantity = quantity_data.get("value", 0)
    selected_unit = product.get("selectedPurchasingUnit")
    supports_dual = bool(product.get("supportsBothEachAndKgPricing"))
    average_weight = product.get("averageWeightPerUnit")

    if supports_dual and selected_unit == "Each":
        count = _estimate_each_count(stored_quantity, average_weight)
        if isinstance(count, int):
            return (
                f"{count} each approx. "
                f"(stored as {_format_kg(stored_quantity)}kg)"
            )
        return f"Each purchase (stored as {_format_kg(stored_quantity)}kg)"

    unit_label = selected_unit or product.get("unit") or "Each"
    if unit_label == "Kg":
        return f"{_format_kg(stored_quantity)}kg"
    if float(stored_quantity).is_integer():
        return f"{int(stored_quantity)}x"
    return f"{stored_quantity}x"


@click.group()
@click.option("--no-input", is_flag=True, help="Disable all prompts")
@click.option("-q", "--quiet", is_flag=True, help="Minimal output")
@click.option("-d", "--debug", is_flag=True, help="Show stack traces")
@click.version_option(version=__version__)
@click.pass_context
def main(ctx, no_input, quiet, debug):
    """Woolworths NZ grocery management CLI.

    USAGE
      woolies <command> [options] <args>

    EXAMPLES
      woolies search "milk"
      woolies cart add 123456 1
      woolies cart list --json
      woolies doctor

    CONFIGURATION
      Set WOOLWORTHS_USERNAME and WOOLWORTHS_PASSWORD environment variables,
      or create a config file at ~/.config/woolies-nz-cli/config.toml.

    NOT AFFILIATED with Woolworths Limited or Woolworths NZ Limited.
    Use at your own risk.
    """
    maybe_show_banner()
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "no_input": no_input,
            "quiet": quiet,
            "debug": debug,
        }
    )


def _print_products(products):
    """Print grouped product list."""
    groups = {}
    for p in products:
        key = (p["brand"], p["name"])
        if key not in groups:
            groups[key] = []
        groups[key].append(p)

    click.echo(f"Found {len(products)} products ({len(groups)} groups):\n")

    for (brand, name), variants in groups.items():
        display_name = name
        if brand and name.lower().startswith(brand.lower()):
            display_name = name[len(brand) :].strip()

        title = f"{brand} {display_name}".strip().title()
        click.secho(title, bold=True, fg="cyan")

        for p in variants:
            variant_line = []
            if p["size"]:
                size_str = p["size"]
                if p.get("package_type"):
                    size_str = f"{size_str} ({p['package_type']})"
                variant_line.append(f"Size: {size_str}")

            price_str = f"${p['price']:.2f}"
            if p["is_special"] and p["sale_price"]:
                price_str = f"${p['sale_price']:.2f} (Special, was ${p['price']:.2f})"
            variant_line.append(f"Price: {price_str}")

            click.echo(f"  - {' | '.join(variant_line)}")

            click.echo(f"    SKU: {p['sku']} | ", nl=False)
            stock_color = "green" if p["in_stock"] else "red"
            click.secho(p["availability"], fg=stock_color, nl=False)
            if p["category"]:
                click.echo(f" | Category: {p['category']}")
            else:
                click.echo("")

            if p["cup_price"] and p["cup_measure"]:
                unit_str = f"    Unit: {p['unit']} "
                unit_str += f"(${p['cup_price']:.2f} per {p['cup_measure']})"
                click.echo(unit_str)
            else:
                click.echo(f"    Unit: {p['unit']}")
            if p.get("supports_dual_pricing"):
                click.echo(
                    "    Purchase options: "
                    f"{_format_dual_pricing(p)} | "
                    "use `--unit Each` for item counts"
                )
            click.echo()


@main.command()
@click.argument("query")
@click.option(
    "--limit", type=int, default=10, help="Max number of results (default: 10, max: 48)"
)
@click.option("--size", help="Filter by size (e.g. 2L, 500g)")
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.pass_context
def search(ctx, query: str, limit: int, size: str, json_output: bool):
    """Search for products.

    Example:
        woolies search "milk"
        woolies search "milk" --size 2L
        woolies search "bread whole grain" --json
    """

    async def _search():
        try:
            client = WoolworthsClient()
            products = await client.search(query, limit=limit)

            if size:
                size_lower = size.lower()
                products = [p for p in products if size_lower in p["size"].lower()]

            if json_output:
                output = {"query": query, "count": len(products), "products": products}
                click.echo(json.dumps(output, indent=2))
            else:
                if not products:
                    msg = f"No products found for '{query}'"
                    if size:
                        msg += f" with size matching '{size}'"
                    click.echo(msg)
                    return

                _print_products(products)

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Search failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_search())


@main.group()
def cart():
    """Manage shopping cart."""
    pass


@cart.command()
@click.argument("sku")
@click.argument("quantity", type=float)
@click.option(
    "--unit",
    type=click.Choice(["Each", "Kilogram", "Kg"]),
    default="Each",
    help="Pricing unit",
)
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.pass_context
def add(ctx, sku: str, quantity: float, unit: str, json_output: bool):
    """Add item to cart.

    Note: dual-priced loose produce supports both `Each` item counts and
          `Kilogram` weights. When using `--unit Each`, pass a whole count.

    Example:
        woolies cart add 910393 2
        woolies cart add 123456 0.75 --unit Kilogram
        woolies cart add 135344 3 --unit Each
    """

    async def _add():
        try:
            client = WoolworthsClient()
            result = await client.add_to_cart(sku, quantity, unit)

            if json_output:
                output = {
                    "action": "add",
                    "sku": sku,
                    "quantity": quantity,
                    "unit": unit,
                    "success": True,
                    "result": result,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                dual_pricing = result.get("_dual_pricing")
                if dual_pricing:
                    click.echo(f"✓ Added {int(quantity)} each (SKU: {sku}) to cart")
                    click.echo(
                        "  Woolworths stored: "
                        f"{_format_kg(dual_pricing.get('stored_quantity'))}"
                        f"{dual_pricing.get('stored_unit', '').lower()}"
                    )
                    click.echo(
                        "  Purchase mode: "
                        f"{dual_pricing.get('selected_purchasing_unit')}"
                    )
                    average_weight = dual_pricing.get("average_weight_per_unit")
                    average_price = dual_pricing.get("average_price_per_each")
                    if average_weight is not None:
                        click.echo(
                            f"  Average weight per item: {_format_kg(average_weight)}kg"
                        )
                    if average_price is not None:
                        click.echo(
                            f"  Average price per item: {_format_currency(average_price)}"
                        )
                else:
                    click.echo(f"✓ Added {quantity}x (SKU: {sku}) to cart")
                    click.echo(f"  Unit: {unit}")

                if "_rounding_warning" in result and not ctx.obj.get("quiet"):
                    click.echo(f"  ⚠️  {result['_rounding_warning']}", err=True)

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Add to cart failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_add())


def _print_cart(cart_data):
    """Print cart contents and totals."""
    items_categories = cart_data.get("items", [])

    all_products = []
    for category in items_categories:
        all_products.extend(category.get("products", []))

    if not all_products:
        click.echo("Cart is empty")
        return

    basket_totals = cart_data.get("context", {}).get("basketTotals", {})
    item_count = basket_totals.get("totalItems", len(all_products))

    click.echo(f"Cart ({item_count} items):\n")

    for product in all_products:
        name = product.get("name", "Unknown")
        brand = product.get("brand") or ""
        sku = product.get("sku", "")
        quantity_data = product.get("quantity", {})
        quantity = quantity_data.get("value", 0)
        price = product.get("price", {})
        size = product.get("size", {}).get("volumeSize", "")

        price_str = price.get("total")
        if not price_str:
            extended_list = price.get("extendedListPrice")
            if extended_list:
                price_str = extended_list
            else:
                unit_price = price.get("originalPrice", 0)
                price_str = f"${float(unit_price) * float(quantity):.2f}"

        display_name = name
        if brand and name.lower().startswith(brand.lower()):
            display_name = name[len(brand) :].strip()

        full_name = f"{brand} {display_name}".strip().title()
        if size:
            full_name = f"{full_name} {size}"

        click.echo(f"{_build_cart_line(product)} {full_name}")
        detail_parts = [f"SKU: {sku}", price_str]
        selected_unit = product.get("selectedPurchasingUnit")
        if product.get("supportsBothEachAndKgPricing"):
            detail_parts.append(
                f"Purchase mode: {selected_unit or product.get('unit', 'Kg')}"
            )
            average_weight = product.get("averageWeightPerUnit")
            if selected_unit == "Each" and average_weight is not None:
                detail_parts.append(f"avg wt {_format_kg(average_weight)}kg each")
        click.echo(f"   {' | '.join(detail_parts)}")
        click.echo()

    calculated_subtotal = sum(
        float(price.get("originalPrice", 0)) * float(quantity_data.get("value", 0))
        for product in all_products
        if (price := product.get("price", {}))
        and (quantity_data := product.get("quantity", {}))
    )
    if calculated_subtotal > 0:
        click.echo(f"Subtotal: ${calculated_subtotal:.2f}")
    else:
        subtotal = basket_totals.get("subtotal", "$0.00")
        click.echo(f"Subtotal: {subtotal}")


@cart.command()
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.pass_context
def list(ctx, json_output: bool):
    """View cart contents.

    Example:
        woolies cart list
        woolies cart list --json
    """

    async def _list():
        try:
            client = WoolworthsClient()
            cart_data = await client.get_cart()

            if json_output:
                click.echo(json.dumps(cart_data, indent=2))
            else:
                _print_cart(cart_data)

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Get cart failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_list())


@cart.command()
@click.argument("sku")
@click.argument("quantity", type=float)
@click.option(
    "--unit",
    type=click.Choice(["Each", "Kilogram", "Kg"]),
    default="Each",
    help="Pricing unit",
)
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.pass_context
def update(ctx, sku: str, quantity: float, unit: str, json_output: bool):
    """Update item quantity in cart.

    Example:
        woolies cart update 910393 3
        woolies cart update 123456 0.75 --unit Kilogram
        woolies cart update 135344 4 --unit Each
    """

    async def _update():
        try:
            client = WoolworthsClient()
            result = await client.update_cart_item(sku, quantity, unit)

            if json_output:
                output = {
                    "action": "update",
                    "sku": sku,
                    "quantity": quantity,
                    "unit": unit,
                    "success": True,
                    "result": result,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                dual_pricing = result.get("_dual_pricing")
                if dual_pricing:
                    click.echo(f"✓ Updated SKU {sku} to {int(quantity)} each")
                    click.echo(
                        "  Woolworths stored: "
                        f"{_format_kg(dual_pricing.get('stored_quantity'))}"
                        f"{dual_pricing.get('stored_unit', '').lower()}"
                    )
                else:
                    click.echo(f"✓ Updated SKU {sku} to {quantity}x ({unit})")

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Update cart failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_update())


@cart.command()
@click.argument("sku")
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.pass_context
def remove(ctx, sku: str, json_output: bool):
    """Remove item from cart.

    Example:
        woolies cart remove 910393
    """

    async def _remove():
        try:
            client = WoolworthsClient()
            result = await client.remove_from_cart(sku)

            if json_output:
                output = {
                    "action": "remove",
                    "sku": sku,
                    "success": True,
                    "result": result,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                click.echo(f"✓ Removed SKU {sku} from cart")

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Remove from cart failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_remove())


@cart.command()
@click.option(
    "--json-output", "--json", "json_output", is_flag=True, help="Output JSON"
)
@click.option("--force", "-f", is_flag=True, help="Force clear without confirmation")
@click.pass_context
def clear(ctx, json_output: bool, force: bool):
    """Clear all items from cart.

    Example:
        woolies cart clear --force
    """
    if not force:
        raise click.UsageError("Destructive operation. Use --force to confirm.")

    async def _clear():
        try:
            client = WoolworthsClient()
            result = await client.clear_cart()

            if json_output:
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo(f"✓ {result.get('message', 'Cart cleared')}")

        except AuthError as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Authentication error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Clear cart failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_clear())


@main.command(name="inspect")
@click.pass_context
def inspect(ctx):
    """Launch visible browser for debugging.

    Opens browser with active session. Useful for:
    - Inspecting selectors when login breaks
    - Watching API requests in devtools
    - Testing the login flow end-to-end

    Press Ctrl-C to exit.
    """

    async def _inspect():
        session = BrowserSession(headless=False, slow_mo=100)
        try:
            async with session as page:
                click.echo("Browser launched with active session.")
                click.echo(
                    "Navigate to inspect selectors, test workflows, check API calls."
                )
                click.echo("Press Ctrl-C to exit.\n")

                await page.goto("https://www.woolworths.co.nz")

                try:
                    await page.wait_for_timeout(3600000)
                except KeyboardInterrupt:
                    pass

        except KeyboardInterrupt:
            click.echo("\nClosing browser...")
            sys.exit(130)
        except Exception as e:
            if ctx.obj.get("debug"):
                raise
            click.echo(f"Debug failed: {e}", err=True)
            sys.exit(1)

    try:
        asyncio.run(_inspect())
    except KeyboardInterrupt:
        sys.exit(130)


@main.command()
@click.pass_context
def doctor(ctx):
    """Diagnose installation and configuration."""
    ok = True

    # Credentials
    try:
        username, _ = load_credentials()
        click.secho(f"✓ Credentials found ({username})", fg="green")
    except ConfigError as e:
        click.secho("✗ Credentials not found", fg="red")
        click.echo(f"  {e}")
        ok = False

    # Directories
    for label, path in [("State dir", state_dir()), ("Config dir", config_dir())]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = "writable" if path.exists() else "not writable"
            click.secho(f"✓ {label}: {path} ({writable})", fg="green")
        except OSError as e:
            click.secho(f"✗ {label}: {path}", fg="red")
            click.echo(f"  {e}")
            ok = False

    # Optional config file
    cfg = config_file()
    if cfg.exists():
        click.secho(f"✓ Config file present: {cfg}", fg="green")
    else:
        click.echo(f"  (no config file at {cfg} — using env vars)")

    # Camoufox importable
    try:
        import camoufox  # noqa: F401

        click.secho("✓ Camoufox importable", fg="green")
    except ImportError as e:
        click.secho("✗ Camoufox import failed", fg="red")
        click.echo(f"  {e}")
        ok = False

    # DNS resolves (full HTTP reach is gated by Akamai; only Camoufox can do that)
    import socket

    try:
        ip = socket.gethostbyname("www.woolworths.co.nz")
        click.secho(f"✓ www.woolworths.co.nz resolves ({ip})", fg="green")
    except socket.gaierror as e:
        click.secho("✗ www.woolworths.co.nz did not resolve", fg="red")
        click.echo(f"  {e}")
        ok = False

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
