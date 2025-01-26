from django.db import models
from question.models import Zip

class ProcessedTest(models.Model):
    file_url = models.URLField(max_length=500)
    bubbles = models.JSONField(help_text="Rasmda Aniqlangan Koordinatalar")
    phone_number = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    student_id = models.BigAutoField(primary_key=True)
    total_score = models.FloatField(default=0)
    
    def __str__(self):
        return f"ScannedImage {self.id}: {self.file_url}"
    
class ProcessedTestResult(models.Model):
    student = models.ForeignKey(ProcessedTest, related_name='results', on_delete=models.CASCADE)
    question = models.ForeignKey(Zip, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=10)
    is_correct = models.BooleanField(default=False)
    processed_at = models.DateTimeField(auto_now_add=True)
    score = models.FloatField(default=0)
