from django.contrib.auth.models import AbstractUser
from django.db import models

class Role(models.Model):
    role = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.role

class CustomUser(AbstractUser):
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="utilisateurs"
    )
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    is_validated_by_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username
