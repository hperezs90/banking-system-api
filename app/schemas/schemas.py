from __future__ import annotations
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── AUTH ────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


# ─── USERS ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    nombre: str   = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    telefono: Optional[str] = None
    dpi: Optional[str]      = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe tener al menos una mayúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe tener al menos un número")
        return v


class UserResponse(BaseModel):
    id:         UUID
    nombre:     str
    apellido:   str
    email:      str
    telefono:   Optional[str]
    rol:        str
    activo:     bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


# ─── ACCOUNTS ────────────────────────────────────────────────

class AccountCreate(BaseModel):
    tipo_cuenta: str  = Field(..., pattern="^(monetaria|ahorro|corriente)$")
    moneda:      str  = Field("GTQ", pattern="^(GTQ|USD)$")
    saldo_inicial: Decimal = Field(Decimal("0.00"), ge=0)


class AccountResponse(BaseModel):
    id:            UUID
    numero_cuenta: str
    tipo_cuenta:   str
    saldo:         Decimal
    moneda:        str
    estado:        str
    created_at:    datetime

    model_config = {"from_attributes": True}


class AccountWithUser(AccountResponse):
    user_id: UUID


# ─── TRANSACTIONS ─────────────────────────────────────────────

class TransferCreate(BaseModel):
    cuenta_destino_numero: str = Field(..., description="Número de cuenta destino")
    monto: Decimal = Field(..., gt=0, description="Monto a transferir")
    descripcion: Optional[str] = Field(None, max_length=255)


class DepositCreate(BaseModel):
    cuenta_destino_numero: str
    monto: Decimal = Field(..., gt=0)
    descripcion: Optional[str] = Field(None, max_length=255)


class WithdrawCreate(BaseModel):
    cuenta_origen_numero: str
    monto: Decimal = Field(..., gt=0)
    descripcion: Optional[str] = Field(None, max_length=255)


class TransactionResponse(BaseModel):
    id:                UUID
    cuenta_origen_id:  Optional[UUID]
    cuenta_destino_id: Optional[UUID]
    monto:             Decimal
    tipo:              str
    estado:            str
    descripcion:       Optional[str]
    referencia:        str
    created_at:        datetime
    procesado_at:      Optional[datetime]

    model_config = {"from_attributes": True}


# ─── STATEMENTS ───────────────────────────────────────────────

class StatementResponse(BaseModel):
    id:                 UUID
    account_id:         UUID
    mes:                int
    anio:               int
    saldo_inicial:      Decimal
    saldo_final:        Decimal
    total_debitos:      Decimal
    total_creditos:     Decimal
    num_transacciones:  int
    generado_at:        datetime

    model_config = {"from_attributes": True}


# ─── GENERICS ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail:  Optional[str] = None


class PaginatedResponse(BaseModel):
    total:  int
    page:   int
    size:   int
    items:  List
