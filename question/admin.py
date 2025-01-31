from django.contrib import admin
from .models import QuestionList, Question, Zip

class QuestionListAdmin(admin.ModelAdmin):
    list_display = ('id', 'list_id')  # Admin panelda ko'rinadigan ustunlar
    search_fields = ('list_id',)  # Qidirish maydonchasi
    actions = ['delete_selected_data']
    def delete_selected_data(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} ta malumot muvaffaqiyatli o'chirildi.")

    delete_selected_data.short_description = 'Tanlangan barcha malumot kodlarni o‘chirish'


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'list', 'true_answer')  # Ko'rinadigan ustunlar
    search_fields = ['true_answer']  # Qidirish maydonchalari
    actions = ['delete_selected_data']
    def delete_selected_data(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} ta malumot muvaffaqiyatli o'chirildi.")

    delete_selected_data.short_description = 'Tanlangan barcha malumot kodlarni o‘chirish'

# Ro'yxatdan o'tkazish
admin.site.register(Zip)
admin.site.register(QuestionList, QuestionListAdmin)
admin.site.register(Question, QuestionAdmin)
