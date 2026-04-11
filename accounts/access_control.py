from django.db.models import QuerySet
from django.utils import timezone


def _current_time():
    return timezone.now()


def _normalize_scope_values(values):
    normalized = []
    for value in values:
        cleaned = " ".join(str(value or "").strip().split())
        if cleaned:
            normalized.append(cleaned)
    return sorted(set(normalized))


def get_admin_scope_profile(user):
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "role", None) not in ("subadmin", "sales"):
        return None
    return getattr(user, "subadmin_profile", None)


def has_admin_portal_access(user, at_time=None):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", None) == "superadmin":
        return True

    profile = get_admin_scope_profile(user)
    if not profile:
        return False
    return profile.is_account_access_active(at_time=at_time or _current_time())


def get_profile_scope_values(profile):
    if not profile:
        return {
            "birth_states": [],
            "college_states": [],
            "passing_years": [],
        }

    return {
        "birth_states": _normalize_scope_values(
            profile.birth_state_scopes.values_list("state_name", flat=True)
        ),
        "college_states": _normalize_scope_values(
            profile.college_state_scopes.values_list("state_name", flat=True)
        ),
        "passing_years": _normalize_scope_values(
            profile.passing_year_scopes.values_list("passing_year", flat=True)
        ),
    }


def has_configured_data_scope(profile):
    values = get_profile_scope_values(profile)
    return all(values[key] for key in ("birth_states", "college_states", "passing_years"))


def filter_preapplications_for_user(user, queryset: QuerySet):
    if getattr(user, "role", None) == "superadmin":
        return queryset

    profile = get_admin_scope_profile(user)
    if not profile or not profile.is_account_access_active():
        return queryset.none()

    scope_values = get_profile_scope_values(profile)
    if not all(scope_values[key] for key in ("birth_states", "college_states", "passing_years")):
        return queryset.none()

    return queryset.filter(
        birthplace_state__in=scope_values["birth_states"],
        college_state__in=scope_values["college_states"],
        passing_year__in=scope_values["passing_years"],
    )


def filter_students_for_user(user, queryset: QuerySet):
    if getattr(user, "role", None) == "superadmin":
        return queryset

    profile = get_admin_scope_profile(user)
    if not profile or not profile.is_account_access_active():
        return queryset.none()

    scope_values = get_profile_scope_values(profile)
    if not all(scope_values[key] for key in ("birth_states", "college_states", "passing_years")):
        return queryset.none()

    return queryset.filter(
        personal_detail__birthplace_state__in=scope_values["birth_states"],
        education__college_state__in=scope_values["college_states"],
        education__passing_year__in=scope_values["passing_years"],
    )


def filter_applications_for_user(user, queryset: QuerySet):
    if getattr(user, "role", None) == "superadmin":
        return queryset

    profile = get_admin_scope_profile(user)
    if not profile or not profile.is_account_access_active():
        return queryset.none()

    scope_values = get_profile_scope_values(profile)
    if not all(scope_values[key] for key in ("birth_states", "college_states", "passing_years")):
        return queryset.none()

    return queryset.filter(
        student__personal_detail__birthplace_state__in=scope_values["birth_states"],
        student__education__college_state__in=scope_values["college_states"],
        student__education__passing_year__in=scope_values["passing_years"],
    )
