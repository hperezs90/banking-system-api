from uuid import UUID
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AuditLog


async def log_action(
    db: AsyncSession,
    accion: str,
    user_id: Optional[UUID] = None,
    tabla_afectada: Optional[str] = None,
    registro_id: Optional[UUID] = None,
    datos_antes: Optional[Any] = None,
    datos_despues: Optional[Any] = None,
    ip_address: Optional[str] = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        accion=accion,
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
        ip_address=ip_address,
    )
    db.add(entry)
    # No hacemos commit aquí, se maneja en el ciclo de vida del request
