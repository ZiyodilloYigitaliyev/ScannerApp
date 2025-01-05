from django.db import models

class QuestionList(models.Model):
    list_id = models.IntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __int__(self):
        return self.list_id
class Question(models.Model):
    list = models.ForeignKey(QuestionList, related_name='questions', on_delete=models.CASCADE)
    category = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    options = models.TextField(blank=True)  # Savol variantlari JSON ko'rinishida
    question_id = models.IntegerField()
    image = models.URLField(null=True, blank=True)
    true_answer = models.CharField(max_length=1)
    def __int__(self):
        return self.question_id
