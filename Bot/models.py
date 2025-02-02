from django.db import models

class BotUser(models.Model):
    user_id = models.BigIntegerField(unique=True)  # Telegram foydalanuvchi ID
    phone_number = models.CharField(max_length=15)  # Foydalanuvchi telefon raqami
    created_at = models.DateTimeField(auto_now_add=True)  # Ro'yxatdan o'tgan vaqti

    def __str__(self):
        return f"User {self.user_id} - {self.phone_number}"

class ChannelStats(models.Model):
    channel_id = models.BigIntegerField(unique=True)  # Kanal ID
    channel_name = models.CharField(max_length=255)  # Kanal nomi
    username = models.CharField(max_length=255, blank=True, null=True)  # Username (optional)
    description = models.TextField(blank=True, null=True)  # Kanal ta'rifi (optional)
    member_count = models.IntegerField()  # A’zolar soni
    updated_at = models.DateTimeField(auto_now=True)  # Oxirgi yangilanish vaqti

    def __str__(self):
        return f"{self.channel_name} - {self.member_count} members"