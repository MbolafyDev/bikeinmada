from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from .models import CustomUser, Role

class RoleAdmin(admin.ModelAdmin):
    list_display = ('role',)  

admin.site.register(Role, RoleAdmin)

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'role', 'is_active', 'is_validated_by_admin', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active', 'is_validated_by_admin', 'is_superuser')
    search_fields = ('username', 'email', 'role__role')

    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'adresse', 'telephone', 'is_validated_by_admin')}),
    )

    def save_model(self, request, obj, form, change):
        if change:
            previous = CustomUser.objects.get(pk=obj.pk)
            # S'assurer que c’est une validation récente
            if not previous.is_validated_by_admin and obj.is_validated_by_admin:
                obj.is_active = True  # Activation automatique
                send_mail(
                    subject="Votre compte a été activé",
                    message="Votre compte a été validé par un administrateur. Vous pouvez maintenant vous connecter.",
                    from_email=None,
                    recipient_list=[obj.email],
                )
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
