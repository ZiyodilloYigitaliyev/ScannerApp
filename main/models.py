from django.db import models
from question.models import Zip

class ProcessedTest(models.Model):
    student_id = models.BigAutoField(primary_key=True)
    total_score = models.FloatField(default=0)
    image_url = models.URLField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.student_id}"
    
class ProcessedTestResult(models.Model):
    student = models.ForeignKey(ProcessedTest, related_name='results', on_delete=models.CASCADE)
    # question_id = models.IntegerField(db_column="question_id")
    question = models.ForeignKey(Zip, on_delete=models.CASCADE)
    student_answer = models.CharField(max_length=10)
    is_correct = models.BooleanField(default=False)
    processed_at = models.DateTimeField(auto_now_add=True)
    score = models.FloatField(default=0)
