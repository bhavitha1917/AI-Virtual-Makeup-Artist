import json

import pytest

from src.core.enums import RECOMMENDABLE_CATEGORIES, Category, VerificationStatus
from src.core.errors import CatalogError
from src.data.loader import load_catalog, read_json
from src.data.schema import parse_catalog


def issues_of(products, shades) -> list[str]:
    with pytest.raises(CatalogError) as exc:
        parse_catalog(products, shades)
    return exc.value.issues


def test_production_catalog_is_valid_and_labelled_demo():
    catalog = load_catalog()
    assert catalog.is_demo
    assert "fictional" in catalog.notice.lower()
    for product in catalog.products.values():
        assert product.verification_status is VerificationStatus.DEMO
        assert product.price is None and product.product_url is None
    for category in RECOMMENDABLE_CATEGORIES:
        assert catalog.products_in(category), f"no products for {category}"


def test_fixture_catalog_valid(test_catalog):
    assert "fx-foundation-a" in test_catalog.products
    assert test_catalog.shades["fx-foundation-a-medium-none"].undertone is None


def test_invalid_json_reports_line(tmp_path):
    bad = tmp_path / "products.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(CatalogError) as exc:
        read_json(bad)
    assert "invalid JSON" in exc.value.issues[0]


def test_missing_file(tmp_path):
    with pytest.raises(CatalogError, match="file not found"):
        load_catalog(tmp_path)


def test_missing_required_field(docs):
    products, shades = docs
    del products["products"][0]["brand"]
    assert any("brand: missing required field" in i for i in issues_of(products, shades))


def test_duplicate_product_id(docs):
    products, shades = docs
    products["products"].append(dict(products["products"][0]))
    assert any("duplicate product id" in i for i in issues_of(products, shades))


def test_duplicate_shade_id(docs):
    products, shades = docs
    shades["shades"].append(dict(shades["shades"][0]))
    assert any("duplicate shade id" in i for i in issues_of(products, shades))


def test_invalid_category(docs):
    products, shades = docs
    products["products"][0]["category"] = "perfume"
    assert any("invalid value 'perfume'" in i for i in issues_of(products, shades))


def test_broken_product_to_shade_reference(docs):
    products, shades = docs
    products["products"][0]["shade_ids"].append("fx-does-not-exist")
    assert any("references missing shade" in i for i in issues_of(products, shades))


def test_broken_shade_to_product_reference(docs):
    products, shades = docs
    shades["shades"][0]["product_id"] = "fx-ghost"
    issues = issues_of(products, shades)
    assert any("references missing product" in i for i in issues)


def test_unverified_product_cannot_carry_price(docs):
    products, shades = docs
    products["products"][0]["price"] = 19.99
    assert any("must be null unless verified" in i for i in issues_of(products, shades))


def test_swatch_only_for_demo(docs):
    products, shades = docs
    row = next(s for s in shades["shades"] if s["verification_status"] == "unverified")
    row["illustrative_swatch_hex"] = "#AABBCC"
    assert any("only allowed for demo" in i for i in issues_of(products, shades))


def test_complexion_shade_requires_depth(docs):
    products, shades = docs
    shades["shades"][0]["depth"] = None
    assert any("must list a depth" in i for i in issues_of(products, shades))


def test_corrector_requires_target(docs):
    products, shades = docs
    row = next(s for s in shades["shades"] if s["product_id"] == "fx-corrector")
    row["correction_target"] = None
    assert any("correction_target" in i for i in issues_of(products, shades))


def test_missing_optional_metadata_is_allowed(docs):
    products, shades = docs
    products["products"][0]["finish"] = None
    products["products"][0]["coverage"] = None
    catalog = parse_catalog(products, shades)
    assert catalog.products["fx-foundation-a"].finish is None


def test_unverified_status_is_preserved(test_catalog):
    shade = test_catalog.shades["fx-foundation-c-medium-neutral"]
    assert shade.verification_status is VerificationStatus.UNVERIFIED


def test_all_issues_collected_at_once(docs):
    products, shades = docs
    products["products"][0]["category"] = "perfume"
    products["products"][1]["finish"] = "sparkly"
    assert len(issues_of(products, shades)) >= 2


def test_top_level_must_be_object():
    issues = issues_of([], {"shades": []})
    assert any("top-level document" in i for i in issues)


def test_production_json_has_no_real_prices_or_urls():
    from src.config import DATA_DIR

    raw = json.loads((DATA_DIR / "products.json").read_text(encoding="utf-8"))
    assert raw["catalog_type"] == "demonstration"
    assert all(p["product_url"] is None and p["price"] is None for p in raw["products"])


def test_every_routine_category_has_catalog_products():
    catalog = load_catalog()
    missing = [c for c in Category if not catalog.products_in(c)]
    assert missing == [], missing
