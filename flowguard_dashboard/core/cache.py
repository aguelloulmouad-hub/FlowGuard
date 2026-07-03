# flowguard_dashboard/core/cache.py
# ─── Cache TTL thread-safe pour les requêtes Neo4j ───

import time
import threading
import functools


class TTLCache:
    """Cache thread-safe avec Time-To-Live (TTL) en secondes."""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        """Retourne la valeur cachée ou None si expirée/inexistante."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if time.time() > expire_at:
                del self._store[key]
                return None
            return value

    def set(self, key, value, ttl=8):
        """Stocke une valeur avec un TTL en secondes."""
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def clear(self):
        """Vide tout le cache."""
        with self._lock:
            self._store.clear()


# ─── Instance globale ───
_cache = TTLCache()


def cached(ttl=8):
    """
    Décorateur pour cacher le résultat d'une méthode pendant `ttl` secondes.
    La clé de cache est basée sur le nom de la fonction et ses arguments.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Construire une clé unique à partir du nom de la fonction et des arguments
            # On ignore 'self' (args[0]) pour les méthodes d'instance
            cache_args = args[1:] if args else args
            key_parts = [func.__name__]
            key_parts.extend(str(a) for a in cache_args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = "|".join(key_parts)

            # Vérifier le cache
            result = _cache.get(cache_key)
            if result is not None:
                return result

            # Appel réel
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper
    return decorator
