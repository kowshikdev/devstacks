from dataclasses import dataclass


class TenantAccessError(ValueError):
    """Raised when an operation targets a profile outside the caller tenant."""


@dataclass(frozen=True)
class TenantContext:
    profile_id: str

    def require_profile(self, profile_id: str) -> None:
        """Reject caller-controlled profile IDs outside the authenticated tenant."""
        if not profile_id or profile_id != self.profile_id:
            raise TenantAccessError("profile does not belong to the authenticated tenant")