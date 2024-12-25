from django.db import models

class ProcessedTest(models.Model):
    student_id = models.IntegerField()
    question_id = models.IntegerField()
    student_answer = models.CharField(max_length=10)
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
   
    def __str__(self):
        return f"{self.student_id} ({self.created_at})"
