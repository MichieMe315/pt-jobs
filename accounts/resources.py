from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, BooleanWidget
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()

class UserProfileResource(resources.ModelResource):
    # Map related user via username for import/export
    username = fields.Field(
        column_name="username",
        attribute="user",
        widget=ForeignKeyWidget(User, "username"),
    )

    # Extra export-only columns
    email = fields.Field(column_name="email")
    approved = fields.Field(column_name="approved", widget=BooleanWidget())

    class Meta:
        model = UserProfile
        # We identify rows by username
        import_id_fields = ("username",)
        fields = (
            "username",        # FK → user by username
            "role",
            "company_name",
            "website",
            "bio",
        )
        export_order = (
            "username",
            "email",
            "approved",
            "role",
            "company_name",
            "website",
            "bio",
        )
        skip_unchanged = True
        report_skipped = True

    # Dehydrate computed fields for export
    def dehydrate_email(self, obj):
        return obj.user.email if obj.user else ""

    def dehydrate_approved(self, obj):
        return bool(obj.user and obj.user.is_active)
