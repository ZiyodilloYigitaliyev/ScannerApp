from django.db import models

class UploadedFile(models.Model):
    name = models.CharField(max_length=255)
    s3_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Question(models.Model):
    text = models.TextField()  # Savol matni
    correct_answer = models.CharField(max_length=10)  # To'g'ri javob
    answerA = models.CharField(max_length=10, blank=True)
    answerB = models.CharField(max_length=10, blank=True)
    answerC = models.CharField(max_length=10, blank=True)
    answerD = models.CharField(max_length=10, blank=True)
    image = models.ImageField(upload_to='questions_images/', blank=True, null=True)  # Rasm (agar mavjud bo'lsa)

    def __str__(self):
        return self.text


