import pytest

from devstacks_domain import TenantAccessError, TenantContext


def test_tenant_context_accepts_its_authenticated_profile():
    TenantContext(profile_id="profile-1").require_profile("profile-1")


@pytest.mark.parametrize("profile_id", ["", "profile-2"])
def test_tenant_context_rejects_foreign_or_empty_profile_ids(profile_id):
    with pytest.raises(TenantAccessError, match="authenticated tenant"):
        TenantContext(profile_id="profile-1").require_profile(profile_id)