import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Numeric,
    SmallInteger, Integer, ForeignKey, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre        = Column(String(100), nullable=False)
    apellido      = Column(String(100), nullable=False)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    telefono      = Column(String(20))
    dpi           = Column(String(20), unique=True)
    rol           = Column(String(20), nullable=False, default="cliente")
    activo        = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at    = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow)

    accounts  = relationship("Account", back_populates="user")
    audit_log = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        CheckConstraint("rol IN ('cliente', 'admin', 'auditor')", name="chk_user_rol"),
    )


class Account(Base):
    __tablename__ = "accounts"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    numero_cuenta  = Column(String(20), nullable=False, unique=True, index=True)
    tipo_cuenta    = Column(String(20), nullable=False)
    saldo          = Column(Numeric(15, 2), nullable=False, default=0.00)
    moneda         = Column(String(3), nullable=False, default="GTQ")
    estado         = Column(String(20), nullable=False, default="activa")
    created_at     = Column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at     = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow)

    user               = relationship("User", back_populates="accounts")
    transactions_origen   = relationship("Transaction", foreign_keys="Transaction.cuenta_origen_id", back_populates="cuenta_origen")
    transactions_destino  = relationship("Transaction", foreign_keys="Transaction.cuenta_destino_id", back_populates="cuenta_destino")
    statements         = relationship("Statement", back_populates="account")

    __table_args__ = (
        CheckConstraint("tipo_cuenta IN ('monetaria', 'ahorro', 'corriente')", name="chk_tipo_cuenta"),
        CheckConstraint("estado IN ('activa', 'inactiva', 'bloqueada', 'cerrada')", name="chk_estado_cuenta"),
        CheckConstraint("moneda IN ('GTQ', 'USD')", name="chk_moneda"),
        CheckConstraint("saldo >= 0", name="chk_saldo_positivo"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuenta_origen_id  = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True)
    cuenta_destino_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True)
    monto             = Column(Numeric(15, 2), nullable=False)
    tipo              = Column(String(30), nullable=False)
    estado            = Column(String(20), nullable=False, default="pendiente")
    descripcion       = Column(String(255))
    referencia        = Column(String(50), unique=True)
    created_at        = Column(DateTime(timezone=True), server_default=text("NOW()"))
    procesado_at      = Column(DateTime(timezone=True))

    cuenta_origen  = relationship("Account", foreign_keys=[cuenta_origen_id], back_populates="transactions_origen")
    cuenta_destino = relationship("Account", foreign_keys=[cuenta_destino_id], back_populates="transactions_destino")

    __table_args__ = (
        CheckConstraint("tipo IN ('transferencia', 'deposito', 'retiro', 'pago', 'cargo')", name="chk_tipo_tx"),
        CheckConstraint("estado IN ('pendiente', 'completada', 'fallida', 'revertida')", name="chk_estado_tx"),
        CheckConstraint("monto > 0", name="chk_monto_positivo"),
    )


class Statement(Base):
    __tablename__ = "statements"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id          = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    mes                 = Column(SmallInteger, nullable=False)
    anio                = Column(SmallInteger, nullable=False)
    saldo_inicial       = Column(Numeric(15, 2), nullable=False, default=0.00)
    saldo_final         = Column(Numeric(15, 2), nullable=False, default=0.00)
    total_debitos       = Column(Numeric(15, 2), nullable=False, default=0.00)
    total_creditos      = Column(Numeric(15, 2), nullable=False, default=0.00)
    num_transacciones   = Column(Integer, nullable=False, default=0)
    generado_at         = Column(DateTime(timezone=True), server_default=text("NOW()"))

    account = relationship("Account", back_populates="statements")

    __table_args__ = (
        CheckConstraint("mes BETWEEN 1 AND 12", name="chk_mes"),
        CheckConstraint("anio >= 2020", name="chk_anio"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accion          = Column(String(100), nullable=False)
    tabla_afectada  = Column(String(50))
    registro_id     = Column(UUID(as_uuid=True))
    datos_antes     = Column(JSONB)
    datos_despues   = Column(JSONB)
    ip_address      = Column(String(45))
    created_at      = Column(DateTime(timezone=True), server_default=text("NOW()"))

    user = relationship("User", back_populates="audit_log")
