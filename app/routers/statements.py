from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.database import get_db
from app.models.models import User, Account, Transaction, Statement
from app.schemas.schemas import StatementResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/statements", tags=["Estados de Cuenta"])


@router.post("/generate/{account_id}", response_model=StatementResponse, status_code=201)
async def generate_statement(
    account_id: str,
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2020),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verificar que la cuenta pertenece al usuario
    acc_result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Verificar que no existe ya un estado para ese período
    existing = await db.execute(
        select(Statement).where(
            Statement.account_id == account_id,
            Statement.mes == mes,
            Statement.anio == anio,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un estado de cuenta para {mes}/{anio}",
        )

    # Calcular totales del período
    tx_result = await db.execute(
        select(Transaction).where(
            or_(
                Transaction.cuenta_origen_id == account_id,
                Transaction.cuenta_destino_id == account_id,
            ),
            Transaction.estado == "completada",
            func.extract("month", Transaction.created_at) == mes,
            func.extract("year",  Transaction.created_at) == anio,
        )
    )
    transactions = tx_result.scalars().all()

    total_debitos = sum(
        float(tx.monto)
        for tx in transactions
        if str(tx.cuenta_origen_id) == account_id
    )
    total_creditos = sum(
        float(tx.monto)
        for tx in transactions
        if str(tx.cuenta_destino_id) == account_id
    )
    saldo_final = float(account.saldo)
    saldo_inicial = saldo_final - total_creditos + total_debitos

    statement = Statement(
        account_id=account_id,
        mes=mes,
        anio=anio,
        saldo_inicial=round(saldo_inicial, 2),
        saldo_final=round(saldo_final, 2),
        total_debitos=round(total_debitos, 2),
        total_creditos=round(total_creditos, 2),
        num_transacciones=len(transactions),
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)
    return statement


@router.get("/{account_id}", response_model=List[StatementResponse])
async def get_statements(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verificar acceso
    acc_result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    result = await db.execute(
        select(Statement)
        .where(Statement.account_id == account_id)
        .order_by(Statement.anio.desc(), Statement.mes.desc())
    )
    return result.scalars().all()
