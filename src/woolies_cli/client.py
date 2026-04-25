"""Woolworths NZ client for search and cart operations."""

from typing import Any, Dict, List, Optional

from .browser import BrowserSession
from .http_client import CookieExpiredError, HTTPClient


class WoolworthsClient:
    """Client for Woolworths NZ operations.

    Uses fast HTTP client by default. Falls back to browser for auth refresh.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.http_client = HTTPClient()

    @staticmethod
    def _normalize_unit(unit: str) -> str:
        """Normalize CLI-friendly pricing units to Woolworths API values."""
        return "Kg" if unit == "Kilogram" else unit

    @staticmethod
    def _parse_product(item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the product fields the CLI needs from API responses."""
        price_info = item.get("price", {})
        size_info = item.get("size", {})
        quantity_info = item.get("quantity", {})
        departments = item.get("departments", [])
        breadcrumb = item.get("breadcrumb", {})

        category = ""
        if departments:
            category = departments[0].get("name", "")
        elif breadcrumb:
            category = breadcrumb.get("department", {}).get("name", "")

        supports_dual_pricing = bool(item.get("supportsBothEachAndKgPricing"))
        average_weight_per_unit = item.get("averageWeightPerUnit")
        average_price_per_each = price_info.get("averagePricePerSingleUnit")

        return {
            "name": item.get("name") or "",
            "brand": item.get("brand") or "",
            "sku": str(item.get("sku", "")),
            "price": price_info.get("originalPrice", 0),
            "sale_price": price_info.get("salePrice"),
            "is_special": price_info.get("isSpecial", False),
            "unit": item.get("unit", "Each"),
            "selected_purchasing_unit": item.get("selectedPurchasingUnit"),
            "size": size_info.get("volumeSize", ""),
            "package_type": size_info.get("packageType"),
            "cup_price": size_info.get("cupPrice"),
            "cup_measure": size_info.get("cupMeasure"),
            "availability": item.get("availabilityStatus", "Unknown"),
            "category": category,
            "in_stock": item.get("availabilityStatus") == "In Stock",
            "supports_dual_pricing": supports_dual_pricing,
            "supports_both_each_and_kg_pricing": supports_dual_pricing,
            "average_weight_per_unit": average_weight_per_unit,
            "average_price_per_each": average_price_per_each,
            "purchasing_unit_price": price_info.get("purchasingUnitPrice"),
            "minimum_quantity": quantity_info.get("min"),
            "maximum_quantity": quantity_info.get("max"),
            "quantity_increment": quantity_info.get("increment"),
            "quantity_in_order": quantity_info.get("quantityInOrder"),
            "purchasing_quantity_string": quantity_info.get(
                "purchasingQuantityString"
            ),
        }

    async def _refresh_cookies(self) -> None:
        """Refresh cookies by logging in via browser."""
        session = BrowserSession(headless=self.headless)
        async with session as page:
            await session.ensure_logged_in(page)
            await page.goto("https://www.woolworths.co.nz")
            await page.wait_for_timeout(2000)

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute function with automatic cookie refresh on auth failure."""
        try:
            return await func(*args, **kwargs)
        except CookieExpiredError:
            await self._refresh_cookies()
            return await func(*args, **kwargs)

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for products using API."""

        async def _search() -> List[Dict[str, Any]]:
            size = min(max(1, limit), 48)

            result = await self.http_client.get(
                "/api/v1/products",
                params={
                    "target": "search",
                    "search": query,
                    "inStockProductsOnly": "false",
                    "size": str(size),
                },
            )

            if not result or "products" not in result:
                return []

            products = []
            for item in result.get("products", {}).get("items", []):
                if item.get("type") != "Product":
                    continue
                products.append(self._parse_product(item))

            filtered = [p for p in products if p["name"] and p["sku"]]
            return filtered[:limit]

        result: List[Dict[str, Any]] = await self._execute_with_retry(_search)
        return result

    async def get_product(self, sku: str) -> Dict[str, Any]:
        """Fetch a single product by SKU."""

        async def _get_product() -> Dict[str, Any]:
            result = await self.http_client.get(f"/api/v1/products/{sku}")
            return self._parse_product(result)

        return await self._execute_with_retry(_get_product)

    async def add_to_cart(
        self, sku: str, quantity: float, unit: str = "Each"
    ) -> Dict[str, Any]:
        """Add item to cart via API.

        Note: Woolworths API rounds decimal quantities for 'Each' items:
            - 0.5 to 1.4 -> rounds to 1
            - 1.5 to 2.4 -> rounds to 2
            - < 0.5 may be rejected or removed
            Kilogram items handle decimals better.
        """
        unit = self._normalize_unit(unit)
        product: Optional[Dict[str, Any]] = None

        if quantity > 0:
            product = await self.get_product(sku)

        rounded_quantity = quantity
        rounding_warning = None

        if (
            unit == "Each"
            and product
            and product.get("supports_dual_pricing")
            and quantity != int(quantity)
        ):
            raise ValueError(
                "Dual-priced loose produce must use whole item counts with "
                "--unit Each (for example: 2, 3, 4). Use --unit Kilogram "
                "for explicit weights."
            )

        if unit == "Each" and quantity != int(quantity):
            rounded_quantity = round(quantity)
            if rounded_quantity != quantity:
                rounding_warning = (
                    f"Note: Quantity {quantity} will be rounded to "
                    f"{rounded_quantity} by Woolworths API"
                )

        async def _add() -> Dict[str, Any]:
            return await self.http_client.post(
                "/api/v1/trolleys/my/items",
                data={"sku": sku, "quantity": str(quantity), "pricingUnit": unit},
            )

        result: Dict[str, Any] = await self._execute_with_retry(_add)

        if rounding_warning:
            result["_rounding_warning"] = rounding_warning

        if product:
            result["_product"] = product
            item_added = result.get("itemAdded", {})
            if product.get("supports_dual_pricing") and unit == "Each":
                result["_dual_pricing"] = {
                    "requested_each_count": int(quantity),
                    "average_weight_per_unit": product.get("average_weight_per_unit"),
                    "stored_quantity": item_added.get("quantity"),
                    "stored_unit": product.get("unit"),
                    "selected_purchasing_unit": item_added.get(
                        "selectedPurchasingUnit"
                    ),
                    "average_price_per_each": product.get("average_price_per_each"),
                }

        return result

    async def get_cart(self) -> Dict[str, Any]:
        """Get current cart contents via API."""

        async def _get() -> Dict[str, Any]:
            return await self.http_client.get("/api/v1/trolleys/my")

        result: Dict[str, Any] = await self._execute_with_retry(_get)
        return result

    async def update_cart_item(
        self, sku: str, quantity: float, unit: str = "Each"
    ) -> Dict[str, Any]:
        """Update quantity of item in cart.

        Uses POST (same as add) - API auto-updates if item exists.
        """
        return await self.add_to_cart(sku, quantity, unit)

    async def remove_from_cart(self, sku: str) -> Dict[str, Any]:
        """Remove item from cart by setting quantity to 0."""
        try:
            return await self.add_to_cart(sku, 0, "Each")
        except Exception as e:
            if "not found" in str(e).lower() or "not in cart" in str(e).lower():
                return {"message": "Item was not in cart or already removed"}
            raise e

    async def clear_cart(self) -> Dict[str, Any]:
        """Clear all items from cart via DELETE API."""

        async def _clear() -> Dict[str, Any]:
            try:
                return await self.http_client.delete("/api/v1/trolleys/my/items")
            except Exception as e:
                if "400" in str(e) or "bad request" in str(e).lower():
                    cart = await self.get_cart()
                    items = cart.get("items", [])
                    all_products = []
                    for category in items:
                        all_products.extend(category.get("products", []))

                    if not all_products:
                        return {"message": "Cart is already empty"}
                raise e

        result: Dict[str, Any] = await self._execute_with_retry(_clear)
        return result
