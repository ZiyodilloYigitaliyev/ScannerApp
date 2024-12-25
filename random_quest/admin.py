from django.contrib import admin
from .models import *

# Register your models here.

class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category", "subject", "text")
    search_fields = ("category", "subject", "text")
    list_filter = ("category", "subject")

admin.site.register(Question, Data)