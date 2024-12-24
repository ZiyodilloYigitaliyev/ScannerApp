from django.db import models
from django.contrib.auth.models import User

class Question(models.Model):
    category = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    text = models.TextField()
    options = models.TextField()
    true_answer = models.CharField(max_length=10, null=True, blank=True)
    image = models.ImageField(upload_to="question_images/", null=True, blank=True)

    def __str__(self):
        return f"{self.category} - {self.subject}: {self.text[:50]}"
