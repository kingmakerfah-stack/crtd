from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken


INVALIDATION_TTL_SECONDS = 24 * 60 * 60
ME_CACHE_TTL_SECONDS = 5 * 60


def _invalidated_key(user_id):
    return f'user:{user_id}:invalidated'


def _me_key(user_id, role=None):
    if role:
        return f'user:{user_id}:me:{role}'
    return f'user:{user_id}:me'


def invalidate_user_session(user_id):
    cache.set(_invalidated_key(user_id), True, timeout=INVALIDATION_TTL_SECONDS)


def is_user_invalidated(user_id):
    return bool(cache.get(_invalidated_key(user_id)))


def clear_user_invalidation(user_id):
    cache.delete(_invalidated_key(user_id))
    clear_user_me_cache(user_id)


def clear_user_me_cache(user_id):
    for role in ('superadmin', 'subadmin', 'sales', 'student', 'admin', 'company'):
        cache.delete(_me_key(user_id, role))
    cache.delete(_me_key(user_id))


def get_cached_me(user_id, role):
    return cache.get(_me_key(user_id, role))


def set_cached_me(user_id, role, payload):
    cache.set(_me_key(user_id, role), payload, timeout=ME_CACHE_TTL_SECONDS)


def get_tokens_for_user(user):
    """Return refresh/access token pair with role claim for frontend UX hints."""
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
