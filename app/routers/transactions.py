import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.database import get_db
from app.models.models import User, Account, Transaction
from app.schemas.schemas import (
    TransferCreate, DepositCreate, WithdrawCreate, TransactionResponse
)
from app.services.auth import get_current_user, require_admin
from app.services.audit import log_action

router = APIRouter(prefix="/api/transactions", tags=["Transacciones"])


async def _get_active_account(db: AsyncSession, numero: str) -> Account:
    result = await db.execute(
        select(Account).where(Account.numero_cuenta == numero)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=f"Cuenta {numero} no encontrada")
    if account.estado != "activa":
        raise HTTPException(status_code=400, detail=f"Cuenta {numero} no está activa")
    return account


@router.post("/transfer", response_model=TransactionResponse, status_code=201)
async def transfer(
    payload: TransferCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Obtener cuentas origen (del usuario actual) y destino
    result = await db.execute(
        select(Account)
        .where(Account.user_id == current_user.id, Account.estado == "activa")
        .order_by(Account.created_at)
        .limit(1)
    )
    # Para transferencia, se usa la primera cuenta activa del usuario
    # En producción el frontend enviaría el número de cuenta origen
    cuenta_origen = result.scalar_one_or_none()
    if not cuenta_origen:
        raise HTTPException(status_code=400, detail="No tenés cuentas activas")

    cuenta_destino = await _get_active_account(db, payload.cuenta_destino_numero)

    if cuenta_origen.id == cuenta_destino.id:
        raise HTTPException(status_code=400, detail="No podés transferir a la misma cuenta")

    if cuenta_origen.saldo < payload.monto:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo insuficiente. Disponible: {cuenta_origen.saldo} {cuenta_origen.moneda}"
        )

    # Operación atómica
    referencia = str(uuid.uuid4()).replace("-", "")[:20].upper()
    tx = Transaction(
        cuenta_origen_id=cuenta_origen.id,
        cuenta_destino_id=cuenta_destino.id,
        monto=payload.monto,
        tipo="transferencia",
        estado="completada",
        descripcion=payload.descripcion,
        referencia=referencia,
        procesado_at=datetime.now(timezone.utc),
    )
    db.add(tx)

    cuenta_origen.saldo  -= payload.monto
    cuenta_destino.saldo += payload.monto

    await log_action(
        db,
        accion="TRANSFERENCIA",
        user_id=current_user.id,
        tabla_afectada="transactions",
        datos_despues={
            "monto": str(payload.monto),
            "origen": cuenta_origen.numero_cuenta,
            "destino": payload.cuenta_destino_numero,
        },
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("/deposit", response_model=TransactionResponse, status_code=201)
async def deposit(
    payload: DepositCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    cuenta = await _get_active_account(db, payload.cuenta_destino_numero)
    referencia = str(uuid.uuid4()).replace("-", "")[:20].upper()

    tx = Transaction(
        cuenta_destino_id=cuenta.id,
        monto=payload.monto,
        tipo="deposito",
        estado="completada",
        descripcion=payload.descripcion or "Depósito en efectivo",
        referencia=referencia,
        procesado_at=datetime.now(timezone.utc),
    )
    db.add(tx)
    cuenta.saldo += payload.monto

    await log_action(
        db,
        accion="DEPOSITO",
        user_id=_admin.id,
        tabla_afectada="transactions",
        datos_despues={"monto": str(payload.monto), "cuenta": cuenta.numero_cuenta},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("/withdraw", response_model=TransactionResponse, status_code=201)
async def withdraw(
    payload: WithdrawCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Account).where(
            Account.numero_cuenta == payload.cuenta_origen_numero,
            Account.user_id == current_user.id,
        )
    )
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada o no es tuya")
    if cuenta.estado != "activa":
        raise HTTPException(status_code=400, detail="Cuenta inactiva")
    if cuenta.saldo < payload.monto:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    referencia = str(uuid.uuid4()).replace("-", "")[:20].upper()
    tx = Transaction(
        cuenta_origen_id=cuenta.id,
        monto=payload.monto,
        tipo="retiro",
        estado="completada",
        descripcion=payload.descripcion or "Retiro en efectivo",
        referencia=referencia,
        procesado_at=datetime.now(timezone.utc),
    )
    db.add(tx)
    cuenta.saldo -= payload.monto

    await log_action(
        db,
        accion="RETIRO",
        user_id=current_user.id,
        tabla_afectada="transactions",
        datos_despues={"monto": str(payload.monto), "cuenta": cuenta.numero_cuenta},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(tx)
    return tx


@router.get("/history", response_model=List[TransactionResponse])
async def my_transaction_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Obtener todas las cuentas del usuario
    acc_result = await db.execute(
        select(Account.id).where(Account.user_id == current_user.id)
    )
    account_ids = [row[0] for row in acc_result.all()]

    if not account_ids:
        return []

    result = await db.execute(
        select(Transaction)
        .where(
            or_(
                Transaction.cuenta_origen_id.in_(account_ids),
                Transaction.cuenta_destino_id.in_(account_ids),
            )
        )
        .order_by(Transaction.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return result.scalars().all()


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return tx
