from django.db import models

class QuestionList(models.Model):
    list_id = models.IntegerField(unique=True, default=100000)
    questions_class = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __int__(self):
        return self.list_id
    
class Question(models.Model):
    list = models.ForeignKey(QuestionList, related_name='questions', on_delete=models.CASCADE)
    category = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    options = models.TextField() 
    true_answer = models.CharField(max_length=1, default="")
    
    def __int__(self):
        return self.question_id

    
class Zip(models.Model):
    text = models.TextField()
    options = models.TextField()
    true_answer = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.text

