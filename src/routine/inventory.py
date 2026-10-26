"""User inventory items and pure inventory operations.

Inventories are immutable tuples stored per session; operations return new tuples.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, replace
from typing import Any

from src.core.enums import Base, Category, Finish, Formulation
from src.core.errors import RoutineError
from src.data.schema import Product, Shade

MAX_NAME_LEN = 80
MAX_BRAND_LEN = 60
MAX_SHADE_LEN = 60
MAX_ITEMS = 60
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class InventoryItem:
    item_id: str
    category: Category
    product_name: str
    brand: str = ""
    shade_name: str | None = None
    finish: Finish | None = None
    formulation: Formulation | None = None
    base: Base | None = None
    source: str = "custom"  # "catalog" | "custom"
    catalog_product_id: str | None = None
    catalog_shade_id: str | None = None

    @property
    def display_name(self) -> str:
        name = f"{self.brand} {self.product_name}".strip()
        return f"{name} — {self.shade_name}" if self.shade_name else name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("category", "finish", "formulation", "base"):
            if data[key] is not None:
                data[key] = data[key].value
        return data


def _clean(value: str | None, field_name: str, max_len: int, required: bool) -> str:
    text = _CONTROL_CHARS.sub("", value or "").strip()
    text = re.sub(r"\s+", " ", text)
    if required and not text:
        raise RoutineError("invalid_item", f"Please enter a {field_name}.")
    if len(text) > max_len:
        raise RoutineError(
            "invalid_item", f"The {field_name} must be {max_len} characters or fewer."
        )
    return text


def _coerce(enum_cls: type, value: Any, field_name: str) -> Any:
    if value in (None, ""):
        return None
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise RoutineError("invalid_item", f"Unknown {field_name}: {value!r}.") from exc


def new_item_id() -> str:
    return uuid.uuid4().hex


def create_custom_item(
    *,
    category: Category | str,
    product_name: str,
    brand: str = "",
    shade_name: str | None = None,
    finish: Finish | str | None = None,
    formulation: Formulation | str | None = None,
    item_id: str | None = None,
) -> InventoryItem:
    """Validate user input and build a custom inventory item.

    Custom items never receive a ``base``: their composition is unknown, so no
    compatibility claims can be made about them.
    """
    cat = _coerce(Category, category, "category")
    if cat is None:
        raise RoutineError("invalid_item", "Please choose a product category.")
    shade = _clean(shade_name, "shade", MAX_SHADE_LEN, required=False) or None
    return InventoryItem(
        item_id=item_id or new_item_id(),
        category=cat,
        product_name=_clean(product_name, "product name", MAX_NAME_LEN, required=True),
        brand=_clean(brand, "brand", MAX_BRAND_LEN, required=False),
        shade_name=shade,
        finish=_coerce(Finish, finish, "finish"),
        formulation=_coerce(Formulation, formulation, "formulation"),
        base=None,
        source="custom",
    )


def item_from_catalog(product: Product, shade: Shade | None, item_id: str | None = None
                      ) -> InventoryItem:
    """Build an inventory item from validated catalog data."""
    if shade is not None and shade.product_id != product.product_id:
        raise RoutineError("invalid_item", "That shade does not belong to the selected product.")
    if product.shade_ids and shade is None:
        raise RoutineError("invalid_item", "Please choose a shade for this product.")
    return InventoryItem(
        item_id=item_id or new_item_id(),
        category=product.category,
        product_name=product.product_name,
        brand=product.brand,
        shade_name=shade.shade_name if shade else None,
        finish=(shade.finish if shade and shade.finish else product.finish),
        formulation=product.formulation,
        base=product.base,
        source="catalog",
        catalog_product_id=product.product_id,
        catalog_shade_id=shade.shade_id if shade else None,
    )


def add_item(inventory: tuple[InventoryItem, ...], item: InventoryItem
             ) -> tuple[InventoryItem, ...]:
    if len(inventory) >= MAX_ITEMS:
        raise RoutineError("inventory_full", f"An inventory can hold at most {MAX_ITEMS} items.")
    if any(existing.item_id == item.item_id for existing in inventory):
        raise RoutineError("duplicate_item", "This item is already in your inventory.")
    if item.source == "catalog" and any(
        e.catalog_product_id == item.catalog_product_id
        and e.catalog_shade_id == item.catalog_shade_id
        for e in inventory
    ):
        raise RoutineError("duplicate_item",
                           "This product and shade are already in your inventory.")
    return (*inventory, item)


def remove_item(inventory: tuple[InventoryItem, ...], item_id: str) -> tuple[InventoryItem, ...]:
    remaining = tuple(i for i in inventory if i.item_id != item_id)
    if len(remaining) == len(inventory):
        raise RoutineError("missing_item", "That item is no longer in your inventory.")
    return remaining


def update_item(inventory: tuple[InventoryItem, ...], item_id: str, **changes: Any
                ) -> tuple[InventoryItem, ...]:
    """Update editable fields of an item.

    Catalog items may only change their shade label (product data stays authoritative);
    custom items may change any user-entered field and are re-validated.
    """
    out: list[InventoryItem] = []
    found = False
    for item in inventory:
        if item.item_id != item_id:
            out.append(item)
            continue
        found = True
        if item.source == "custom":
            merged = {
                "category": item.category, "product_name": item.product_name,
                "brand": item.brand, "shade_name": item.shade_name, "finish": item.finish,
                "formulation": item.formulation,
            }
            unknown = set(changes) - set(merged)
            if unknown:
                raise RoutineError("invalid_item", f"Cannot edit fields: {sorted(unknown)}")
            merged.update(changes)
            out.append(create_custom_item(item_id=item.item_id, **merged))
        else:
            if set(changes) - {"shade_name", "catalog_shade_id", "finish"}:
                raise RoutineError(
                    "invalid_item", "Catalog items can only change their shade; remove and "
                    "re-add the item to change the product.")
            out.append(replace(item, **changes))
    if not found:
        raise RoutineError("missing_item", "That item is no longer in your inventory.")
    return tuple(out)
