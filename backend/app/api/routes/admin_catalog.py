import uuid
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.dependencies import SessionDep, StaffDep
from app.core.errors import not_found
from app.models.entities import Ingredient, InventoryMovement, Product
from app.schemas.admin import ProductInput, ProductPatch, StockAdjustmentInput
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/catalog", tags=["Staff · Catalog"])


def product_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "categoryId": product.category_id,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price": product.price,
        "compareAtPrice": product.compare_at_price,
        "tag": product.tag,
        "tone": product.tone,
        "imageUrl": product.image_url,
        "isAvailable": product.is_available,
        "isFeatured": product.is_featured,
        "sortOrder": product.sort_order,
    }


@router.get("/products")
async def products(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(Product).order_by(Product.sort_order, Product.name))).all()
    return [product_dict(row) for row in rows]


@router.post("/products", status_code=201)
async def create_product(
    payload: ProductInput, request: Request, session: SessionDep, staff: StaffDep
) -> dict[str, Any]:
    product = Product(**payload.model_dump())
    session.add(product)
    await session.flush()
    record_audit(
        session, request, staff, "product.created", "product", str(product.id), after=product_dict(product)
    )
    await session.commit()
    return product_dict(product)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    payload: ProductPatch,
    request: Request,
    session: SessionDep,
    staff: StaffDep,
) -> dict[str, Any]:
    product = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise not_found("Product not found")
    before = product_dict(product)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    record_audit(
        session,
        request,
        staff,
        "product.updated",
        "product",
        str(product.id),
        before=before,
        after=product_dict(product),
    )
    await session.commit()
    return product_dict(product)


@router.get("/inventory")
async def inventory(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(Ingredient).order_by(Ingredient.name))).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "unit": row.unit,
            "quantityOnHand": row.quantity_on_hand,
            "reorderLevel": row.reorder_level,
            "isLow": row.quantity_on_hand <= row.reorder_level,
        }
        for row in rows
    ]


@router.post("/inventory/{ingredient_id}/adjustments")
async def adjust_inventory(
    ingredient_id: uuid.UUID,
    payload: StockAdjustmentInput,
    request: Request,
    session: SessionDep,
    staff: StaffDep,
) -> dict[str, Any]:
    ingredient = await session.scalar(
        select(Ingredient).where(Ingredient.id == ingredient_id).with_for_update()
    )
    if ingredient is None:
        raise not_found("Ingredient not found")
    before = ingredient.quantity_on_hand
    ingredient.quantity_on_hand += payload.quantity_delta
    movement_type = "restock" if payload.quantity_delta > 0 else "adjustment"
    session.add(
        InventoryMovement(
            ingredient_id=ingredient.id,
            type=movement_type,
            quantity=payload.quantity_delta,
            reason=payload.reason,
            actor_id=staff.user_id,
        )
    )
    record_audit(
        session,
        request,
        staff,
        "inventory.adjusted",
        "ingredient",
        str(ingredient.id),
        before={"quantityOnHand": str(before)},
        after={"quantityOnHand": str(ingredient.quantity_on_hand), "reason": payload.reason},
    )
    await session.commit()
    return {"id": ingredient.id, "quantityOnHand": ingredient.quantity_on_hand}
