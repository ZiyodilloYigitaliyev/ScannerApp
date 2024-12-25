from django.contrib import admin
from .models import *

# Admin.py yozish
@admin.register(RandomData)
class RandomDataAdmin(admin.ModelAdmin):
    list_display = ('random_number',)
    search_fields = ('random_number',)

@admin.register(TrueAnswer)
class TrueAnswerAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'true_answer')
    search_fields = ('question_id', 'true_answer')
