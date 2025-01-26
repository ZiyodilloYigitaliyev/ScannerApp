from django.urls import path
from .views import DeleteAllQuestionsView,  ListQuestionsView, FilterQuestionsView, HTMLFromZipView

urlpatterns = [
    path('yuklash/', HTMLFromZipView.as_view(), name='upload_questions'),
    path('question/', FilterQuestionsView.as_view(), name='filter_question'),
    path('questions/', ListQuestionsView.as_view(), name='list_questions'),
    path('delete-all-questions/', DeleteAllQuestionsView.as_view(), name='delete_all_questions'),
]