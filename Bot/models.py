from django.db import models

class BotUser(models.Model):
    user_id = models.BigIntegerField(unique=True)  # Telegram foydalanuvchi ID
    phone_number = models.CharField(max_length=15)  # Foydalanuvchi telefon raqami
    created_at = models.DateTimeField(auto_now_add=True)  # Ro'yxatdan o'tgan vaqti

    def __str__(self):
        return f"User {self.user_id} - {self.phone_number}"

