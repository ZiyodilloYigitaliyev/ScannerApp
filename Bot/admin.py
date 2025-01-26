from django.contrib import admin
from .models import BotUser

@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'phone_number', 'created_at')
    search_fields = ('user_id', 'phone_number')
    ordering = ('-created_at',)