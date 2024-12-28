from django.db import models

class ProcessedTest(models.Model):
    student_id = models.IntegerField()
    image_url = models.URLField(blank=True, null=True)
    def __str__(self):
        return f"{self.student_id}"
    
class  ProcessedTestResult(models.Model):
    student = models.ForeignKey(ProcessedTest, related_name='results', on_delete=models.CASCADE)
    question_id = models.IntegerField()
    student_answer = models.CharField(max_length=10)
    is_correct = models.BooleanField(default=False)
    processed_at = models.DateTimeField(auto_now_add=True)
