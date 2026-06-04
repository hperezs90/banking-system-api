import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import User, Account
from app.schemas.schemas import AccountCreate, AccountResponse, AccountWithUser
from app.services.auth import get_current_user, require_admin
from app.services.audit import log_action
from typing import List

router = APIRouter(prefix="/api/accounts", tags=["Cuentas"])


def _generar_numero_cuenta() -> str:
    year = datetime.utcnow().year
    digits = "".join(random.choices(string.digits, k=8))
    return f"GT{year}{digits}"


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Generar número único
    numero = _generar_numero_cuenta()
    while True:
        existing = await db.execute(select(Account).where(Account.numero_cuenta == numero))
        if not existing.scalar_one_or_none():
            break
        numero = _generar_numero_cuenta()

    account = Account(
        user_id=current_user.id,
        numero_cuenta=numero,
        tipo_cuenta=payload.tipo_cuenta,
        saldo=payload.saldo_inicial,
        moneda=payload.moneda,
        estado="activa",
    )
    db.add(account)
    await db.flush()

    await log_action(
        db,
        accion="CREAR_CUENTA",
        user_id=current_user.id,
        tabla_afectada="accounts",
        registro_id=account.id,
        datos_despues={"numero": numero, "tipo": payload.tipo_cuenta},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(account)
    return account


@router.get("/me", response_model=List[AccountResponse])
async def get_my_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Account)
        .where(Account.user_id == current_user.id)
        .order_by(Account.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Solo admin puede ver cuentas de otros usuarios
    if account.user_id != current_user.id and current_user.rol not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Sin acceso a esta cuenta")

    return account


@router.patch("/{account_id}/estado")
async def update_account_status(
    account_id: str,
    estado: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    estados_validos = ("activa", "inactiva", "bloqueada", "cerrada")
    if estado not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Opciones: {estados_validos}",
        )

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    estado_anterior = account.estado
    account.estado = estado

    await log_action(
        db,
        accion="CAMBIO_ESTADO_CUENTA",
        user_id=_admin.id,
        tabla_afectada="accounts",
        registro_id=account.id,
        datos_antes={"estado": estado_anterior},
        datos_despues={"estado": estado},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    return {"message": f"Estado actualizado a '{estado}'", "account_id": account_id}


@router.get("/admin/all", response_model=List[AccountWithUser])
async def get_all_accounts(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Account).order_by(Account.created_at.desc())
    )
    return result.scalars().all()
