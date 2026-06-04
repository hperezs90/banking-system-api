from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserResponse
from app.services.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/users", tags=["Usuarios"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.activo = not user.activo
    await db.commit()
    status_str = "activado" if user.activo else "desactivado"
    return {"message": f"Usuario {status_str}", "activo": user.activo}
