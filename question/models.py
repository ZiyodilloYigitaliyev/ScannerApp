from django.db import models

# Model yaratish
class RandomData(models.Model):
    random_number = models.IntegerField()
    data = models.JSONField()

class TrueAnswer(models.Model):
    random_number = models.ForeignKey(RandomData, on_delete=models.CASCADE, related_name="true_answers")
    question_id = models.IntegerField(unique=True)
    true_answer = models.CharField(max_length=10)

    def __str__(self):
        return f"TrueAnswer(Question ID: {self.question_id}, Answer: {self.true_answer})"
