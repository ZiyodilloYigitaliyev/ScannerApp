from django.urls import path
from .views import DeleteAllQuestionsView,  ListQuestionsView, PDFUploadView

urlpatterns = [
    path('yuklash/', PDFUploadView.as_view(), name='upload_questions'),
    path('questions/', ListQuestionsView.as_view(), name='list_questions'),
    path('delete-all-questions/', DeleteAllQuestionsView.as_view(), name='delete_all_questions'),
]