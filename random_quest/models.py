from django.db import models

class Question(models.Model):
    category = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    text = models.TextField()
    options = models.JSONField()
    true_answer = models.CharField(max_length=10)
    image = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.text


class Data(models.Model):
    additional_value = models.IntegerField()
    questions = models.ManyToManyField(Question, related_name="data")
