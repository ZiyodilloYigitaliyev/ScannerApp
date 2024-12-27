from django.db import models

class QuestionList(models.Model):
    list_id = models.IntegerField(unique=True)
    def __int__(self):
        return self.list_id
class Question(models.Model):
    list = models.ForeignKey(QuestionList, related_name='questions', on_delete=models.CASCADE)
    question_id = models.IntegerField()
    true_answer = models.CharField(max_length=1)
    def __int__(self):
        return self.question_id
