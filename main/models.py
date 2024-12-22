from django.db import models

class ProcessedTest(models.Model):
    image_url = models.URLField()
    student_id = models.CharField(max_length=50)
    marked_answers = models.JSONField()
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_id} ({self.processed_at})"
