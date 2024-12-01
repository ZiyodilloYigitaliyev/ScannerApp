from django.db import models

class UploadedFile(models.Model):
    name = models.CharField(max_length=255)
    s3_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Question(models.Model):
    text = models.TextField()  # Savol matni
    correct_answer = models.CharField(max_length=255)  # To'g'ri javob
    image = models.ImageField(upload_to='questions_images/', blank=True, null=True)  # Rasm (agar mavjud bo'lsa)

    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)  # Javob matni
    is_correct = models.BooleanField(default=False)  # To'g'ri javobni belgilash

    def __str__(self):
        return self.text
