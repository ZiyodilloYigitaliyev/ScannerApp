from django.contrib import admin
from .models import Data, Question

@admin.register(Data)
class DataAdmin(admin.ModelAdmin):
    list_display = ('id', 'additional_value')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'subject', 'text')
