from django.contrib import admin
from .models import BotUser, ChannelStats

@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'phone_number', 'created_at')
    search_fields = ('user_id', 'phone_number')
    ordering = ('-created_at',)
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'

@admin.register(ChannelStats)
class ChannelStatsAdmin(admin.ModelAdmin):
    list_display = ('channel_name', 'member_count', 'updated_at')
    search_fields = ('channel_name', 'member_count')
    ordering = ('-updated_at',)
    list_filter = ('updated_at',)
    date_hierarchy = 'updated_at'