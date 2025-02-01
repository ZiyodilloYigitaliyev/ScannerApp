from django.urls import path
from .views import DeleteAllQuestionsView,  ListQuestionsView, HTMLFromZipView, BackupDataView

urlpatterns = [
    path('yuklash/', HTMLFromZipView.as_view(), name='upload_questions'),
    path('questions/', ListQuestionsView.as_view(), name='list_questions'),
    path('delete-all-questions/', DeleteAllQuestionsView.as_view(), name='delete_all_questions'),
    path("backup/", BackupDataView.as_view(), name='backup_question'),
]