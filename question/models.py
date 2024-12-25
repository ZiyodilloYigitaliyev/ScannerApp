from django.db import models

# Model yaratish
class RandomData(models.Model):
    random_number = models.IntegerField(unique=True)
    data = models.JSONField()

class TrueAnswer(models.Model):
    question_id = models.IntegerField(unique=True)
    true_answer = models.CharField(max_length=10)
