from django.contrib import admin
from .models import QuestionList, Question

class QuestionListAdmin(admin.ModelAdmin):
    list_display = ('id', 'list_id')  # Admin panelda ko'rinadigan ustunlar
    search_fields = ('list_id',)  # Qidirish maydonchasi


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'list', 'question_id', 'true_answer')  # Ko'rinadigan ustunlar
    search_fields = ('question_id', 'true_answer')  # Qidirish maydonchalari

# Ro'yxatdan o'tkazish
admin.site.register(QuestionList, QuestionListAdmin)
admin.site.register(Question, QuestionAdmin)
