from __future__ import annotations

from enum import StrEnum

TAXONOMY_VERSION = "stylecapture-v1"


class GarmentCategory(StrEnum):
    TOPS = "tops"
    BOTTOMS = "bottoms"
    DRESSES = "dresses"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    BAGS = "bags"
    HEADWEAR = "headwear"
    ACCESSORIES = "accessories"
    BEAUTY_OTHER = "beauty_other"


SUBCATEGORIES: dict[GarmentCategory, frozenset[str]] = {
    GarmentCategory.TOPS: frozenset(
        {"t_shirt", "shirt", "blouse", "knitwear", "sweatshirt", "tank_top", "vest"}
    ),
    GarmentCategory.BOTTOMS: frozenset({"trousers", "jeans", "shorts", "skirt", "leggings"}),
    GarmentCategory.DRESSES: frozenset({"dress", "jumpsuit", "romper"}),
    GarmentCategory.OUTERWEAR: frozenset({"jacket", "coat", "trench_coat", "blazer", "cardigan"}),
    GarmentCategory.SHOES: frozenset({"sneakers", "boots", "loafers", "heels", "sandals", "flats"}),
    GarmentCategory.BAGS: frozenset(
        {"handbag", "shoulder_bag", "crossbody_bag", "backpack", "tote", "clutch"}
    ),
    GarmentCategory.HEADWEAR: frozenset({"cap", "hat", "beanie", "headband"}),
    GarmentCategory.ACCESSORIES: frozenset(
        {"scarf", "belt", "necklace", "earrings", "bracelet", "watch", "glasses"}
    ),
    GarmentCategory.BEAUTY_OTHER: frozenset({"beauty", "other"}),
}


def is_valid_subcategory(category: GarmentCategory, subcategory: str) -> bool:
    return subcategory in SUBCATEGORIES[category]


def taxonomy_prompt() -> str:
    categories = "\n".join(
        f"- {category.value}: {', '.join(sorted(subcategories))}"
        for category, subcategories in SUBCATEGORIES.items()
    )
    return f"Taxonomy {TAXONOMY_VERSION}:\n{categories}"
