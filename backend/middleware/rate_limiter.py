"""
Civilis — Rate limiter
Controla el límite de 1 consulta gratuita por día.
Usa Redis para persistir contadores entre reinicios.
"""
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as aioredis
from loguru import logger

from backend.config import get_settings

settings = get_settings()


class RateLimiter:
    """
    Rate limiter basado en Redis.
    Clave: civilis:rl:{user_key}:{fecha}
    El contador expira automáticamente a medianoche siguiente.
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _make_key(self, user_key: str) -> str:
        """Genera la clave Redis para el día actual."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"civilis:rl:{user_key}:{today}"

    def _seconds_until_midnight(self) -> int:
        """Segundos restantes hasta medianoche UTC."""
        now = datetime.utcnow()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int((midnight - now).total_seconds()) + 60  # +1 min de margen

    async def puede_consultar(self, user_key: str, limit: Optional[int] = None) -> bool:
        """
        Verifica si el usuario puede hacer una consulta.

        Args:
            user_key: Identificador del usuario (email o IP).
            limit: Límite a usar (None = usar el del .env).

        Returns:
            True si puede consultar, False si agotó su límite.
        """
        max_queries = limit if limit is not None else settings.free_daily_limit

        try:
            redis = await self._get_redis()
            key = self._make_key(user_key)
            count = await redis.get(key)
            return (count is None) or (int(count) < max_queries)
        except Exception as e:
            logger.error(f"Error verificando rate limit: {e}")
            return True  # En caso de error, permitir (fail open)

    async def registrar_consulta(self, user_key: str) -> int:
        """
        Registra una consulta realizada.

        Returns:
            Número de consultas realizadas hoy.
        """
        try:
            redis = await self._get_redis()
            key = self._make_key(user_key)
            count = await redis.incr(key)
            if count == 1:
                # Primera consulta del día: establecer TTL hasta medianoche
                ttl = self._seconds_until_midnight()
                await redis.expire(key, ttl)
            return count
        except Exception as e:
            logger.error(f"Error registrando consulta: {e}")
            return 1

    async def consultas_hoy(self, user_key: str) -> int:
        """Retorna el número de consultas realizadas hoy."""
        try:
            redis = await self._get_redis()
            key = self._make_key(user_key)
            count = await redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Error obteniendo consultas de hoy: {e}")
            return 0

    async def consultas_restantes(self, user_key: str, plan_limit: Optional[int] = None) -> int:
        """Retorna consultas restantes para el día."""
        max_q = plan_limit if plan_limit is not None else settings.free_daily_limit
        realizadas = await self.consultas_hoy(user_key)
        return max(0, max_q - realizadas)

    async def reset_usuario(self, user_key: str):
        """Resetea el contador de un usuario (admin only)."""
        try:
            redis = await self._get_redis()
            key = self._make_key(user_key)
            await redis.delete(key)
        except Exception as e:
            logger.error(f"Error reseteando rate limit: {e}")


def get_user_key(ip: str, user_id: Optional[str] = None) -> str:
    """
    Genera la clave de identificación del usuario.
    Si está autenticado usa su ID; si no, usa la IP.
    """
    if user_id:
        return f"user:{user_id}"
    return f"ip:{ip}"


# Singleton global
_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        _limiter_instance = RateLimiter()
    return _limiter_instance
