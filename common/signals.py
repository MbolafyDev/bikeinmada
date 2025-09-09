# common/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.middleware import get_current_user
from common.mixins import AuditMixin 

@receiver(pre_save)
def audit_fields_handler(sender, instance, **kwargs):
    if not isinstance(instance, AuditMixin):
        return

    user = get_current_user()
    # print(f"[SIGNAL] Utilisateur courant détecté : {user}")  # debug

    if instance._state.adding:
        if hasattr(instance, 'created_by') and not instance.created_by:
            instance.created_by = user
    else:
        if hasattr(instance, 'updated_by'):
            instance.updated_by = user
