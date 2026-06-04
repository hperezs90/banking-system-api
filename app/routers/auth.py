from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import User, Account
from app.schemas.schemas import UserCreate, UserResponse, Token
from app.services.auth import hash_password, verify_password, create_access_token
from app.services.audit import log_action
import uuid

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Verificar email duplicado
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    user = User(
        nombre=payload.nombre,
        apellido=payload.apellido,
        email=payload.email,
        password_hash=hash_password(payload.password),
        telefono=payload.telefono,
        dpi=payload.dpi,
        rol="cliente",
    )
    db.add(user)
    await db.flush()  # obtener el id antes del commit

    await log_action(
        db,
        accion="REGISTRO_USUARIO",
        user_id=user.id,
        tabla_afectada="users",
        registro_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        await log_action(
            db,
            accion="LOGIN_FALLIDO",
            tabla_afectada="users",
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )

    token = create_access_token({"sub": str(user.id)})

    await log_action(
        db,
        accion="LOGIN_EXITOSO",
        user_id=user.id,
        tabla_afectada="users",
        registro_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    return {"access_token": token, "token_type": "bearer"}
