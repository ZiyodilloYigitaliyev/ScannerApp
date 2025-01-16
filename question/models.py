from django.db import models
from ckeditor.fields import RichTextField

class QuestionList(models.Model):
    list_id = models.IntegerField(default=100000)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __int__(self):
        return self.list_id
    
class Question(models.Model):
    list = models.ForeignKey(QuestionList, related_name='questions', on_delete=models.CASCADE)
    category = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    options = models.TextField() 
    question_id = models.IntegerField()
    true_answer = models.CharField(max_length=1)
    
    def __int__(self):
        return self.question_id

    
