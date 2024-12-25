from django.contrib import admin
from .models import *

@admin.register(RandomData)
class DataAdmin(admin.ModelAdmin):
    list_display = ('id', 'additional_value')

@admin.register(TrueAnswer)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'subject', 'text')
