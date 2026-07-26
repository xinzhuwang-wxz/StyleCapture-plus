from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from typing import Protocol

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError


@dataclass(frozen=True, slots=True)
class CostGuardLease:
    allowed: bool
    retry_after_seconds: int
    keys: tuple[str, ...] = ()


class CostGuard(Protocol):
    async def acquire(
        self,
        *,
        client_key: str,
        actor_key: str | None,
        capability: str,
    ) -> CostGuardLease: ...

    async def release(self, lease: CostGuardLease) -> None: ...


class CostGuardUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CostGuardLimits:
    window_seconds: int = 600
    per_actor_requests: int = 24
    per_client_requests: int = 80
    global_requests: int = 400
    per_actor_concurrency: int = 1
    per_client_concurrency: int = 3
    global_concurrency: int = 12


_ACQUIRE_SCRIPT = """
local window_ms = tonumber(ARGV[1])
local lease_ms = tonumber(ARGV[2])
local retry_after = math.ceil(window_ms / 1000)

for i = 1, 3 do
  local current = tonumber(redis.call('GET', KEYS[i]) or '0')
  local limit = tonumber(ARGV[2 + i])
  if current >= limit then
    local ttl = redis.call('PTTL', KEYS[i])
    if ttl > 0 then retry_after = math.max(1, math.ceil(ttl / 1000)) end
    return {0, retry_after}
  end
end

for i = 4, 6 do
  local current = tonumber(redis.call('GET', KEYS[i]) or '0')
  local limit = tonumber(ARGV[2 + i])
  if current >= limit then
    local ttl = redis.call('PTTL', KEYS[i])
    if ttl > 0 then retry_after = math.max(1, math.ceil(ttl / 1000)) end
    return {0, retry_after}
  end
end

for i = 1, 3 do
  local value = redis.call('INCR', KEYS[i])
  if value == 1 then redis.call('PEXPIRE', KEYS[i], window_ms) end
end
for i = 4, 6 do
  redis.call('INCR', KEYS[i])
  redis.call('PEXPIRE', KEYS[i], lease_ms)
end
return {1, 0}
"""

_RELEASE_SCRIPT = """
for i = 1, #KEYS do
  local current = tonumber(redis.call('GET', KEYS[i]) or '0')
  if current <= 1 then
    redis.call('DEL', KEYS[i])
  else
    redis.call('DECR', KEYS[i])
  end
end
return 1
"""


class RedisCostGuard:
    """Atomic request-window and in-flight guard for hosted model capabilities."""

    def __init__(
        self,
        redis_url: str,
        *,
        limits: CostGuardLimits | None = None,
        key_prefix: str = "stylecapture:cost-guard",
    ) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._limits = limits or CostGuardLimits()
        self._prefix = key_prefix

    async def acquire(
        self,
        *,
        client_key: str,
        actor_key: str | None,
        capability: str,
    ) -> CostGuardLease:
        actor = actor_key or client_key
        quota_keys = (
            f"{self._prefix}:quota:global",
            f"{self._prefix}:quota:client:{client_key}:{capability}",
            f"{self._prefix}:quota:actor:{actor}:{capability}",
        )
        concurrency_keys = (
            f"{self._prefix}:active:global",
            f"{self._prefix}:active:client:{client_key}:{capability}",
            f"{self._prefix}:active:actor:{actor}:{capability}",
        )
        limits = self._limits
        actor_requests = (
            limits.per_actor_requests if actor_key is not None else limits.per_client_requests
        )
        actor_concurrency = (
            limits.per_actor_concurrency if actor_key is not None else limits.per_client_concurrency
        )
        try:
            result = await self._redis.eval(
                _ACQUIRE_SCRIPT,
                6,
                *(quota_keys + concurrency_keys),
                limits.window_seconds * 1000,
                120_000,
                limits.global_requests,
                limits.per_client_requests,
                actor_requests,
                limits.global_concurrency,
                limits.per_client_concurrency,
                actor_concurrency,
            )
        except RedisError as error:
            raise CostGuardUnavailable("cost guard storage unavailable") from error
        allowed = bool(result[0])
        return CostGuardLease(
            allowed=allowed,
            retry_after_seconds=int(result[1]),
            keys=concurrency_keys if allowed else (),
        )

    async def release(self, lease: CostGuardLease) -> None:
        if not lease.allowed or not lease.keys:
            return
        try:
            await self._redis.eval(_RELEASE_SCRIPT, len(lease.keys), *lease.keys)
        except RedisError:
            # The bounded lease TTL is the fail-safe for a lost release.
            return


def trusted_client_key(request: Request) -> str:
    """Resolve the client address only through a local/private reverse proxy hop."""

    peer = request.client.host if request.client is not None else "unknown"
    try:
        trusted_peer = ip_address(peer).is_private or ip_address(peer).is_loopback
    except ValueError:
        trusted_peer = False
    if trusted_peer:
        forwarded = request.headers.get("X-Forwarded-For", "")
        for candidate in forwarded.split(","):
            candidate = candidate.strip()
            try:
                ip_address(candidate)
            except ValueError:
                continue
            return candidate
    return peer


def costly_capability(method: str, path: str) -> str | None:
    if method != "POST":
        return None
    if path == "/v1/captures" or (path.startswith("/v1/jobs/") and path.endswith("/retry")):
        return "vision"
    if path.startswith("/v1/looks/") and path.endswith("/retry"):
        return "vision"
    if path == "/v1/pixel-trials":
        return "image_generation"
    if path.startswith("/v1/items/") and "/presentations/pixel" in path:
        return "image_generation"
    if path.startswith("/v1/looks/") and path.endswith("/renders"):
        return "image_generation"
    if path.startswith("/v1/outfit-plans") and not path.endswith("/purchase-list"):
        return "reasoning"
    return None
