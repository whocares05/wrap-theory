from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    Category,
    ModifierGroup,
    ModifierOption,
    Product,
    ProductModifierGroup,
)
from app.schemas.public import (
    CategoryResponse,
    MenuResponse,
    ModifierGroupResponse,
    ModifierOptionResponse,
    ProductResponse,
)


async def get_public_menu(session: AsyncSession) -> MenuResponse:
    categories = (
        await session.scalars(
            select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name)
        )
    ).all()
    products = (
        await session.scalars(
            select(Product).where(Product.is_available.is_(True)).order_by(Product.sort_order, Product.name)
        )
    ).all()
    links = (
        await session.execute(
            select(ProductModifierGroup.product_id, ModifierGroup)
            .join(ModifierGroup, ModifierGroup.id == ProductModifierGroup.group_id)
            .where(ModifierGroup.is_active.is_(True))
            .order_by(ModifierGroup.sort_order)
        )
    ).all()
    options = (
        await session.scalars(
            select(ModifierOption)
            .where(ModifierOption.is_available.is_(True))
            .order_by(ModifierOption.sort_order, ModifierOption.name)
        )
    ).all()

    options_by_group: defaultdict[object, list[ModifierOptionResponse]] = defaultdict(list)
    for option in options:
        options_by_group[option.group_id].append(ModifierOptionResponse.model_validate(option))
    groups_by_product: defaultdict[object, list[ModifierGroupResponse]] = defaultdict(list)
    for product_id, group in links:
        groups_by_product[product_id].append(
            ModifierGroupResponse(
                id=group.id,
                name=group.name,
                min_selections=group.min_selections,
                max_selections=group.max_selections,
                options=options_by_group[group.id],
            )
        )
    products_by_category: defaultdict[object, list[ProductResponse]] = defaultdict(list)
    for product in products:
        response = ProductResponse.model_validate(product)
        response.modifier_groups = groups_by_product[product.id]
        products_by_category[product.category_id].append(response)
    return MenuResponse(
        categories=[
            CategoryResponse(
                id=category.id,
                name=category.name,
                slug=category.slug,
                products=products_by_category[category.id],
            )
            for category in categories
        ]
    )
