# Generated by Django 5.1.4 on 2024-12-21 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessedImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_url', models.URLField()),
                ('student_id', models.CharField(max_length=50)),
                ('marked_answers', models.JSONField()),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]