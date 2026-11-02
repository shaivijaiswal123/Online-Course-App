class Question(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    question_text = models.CharField(max_length=30)
    mark = models.IntegerField()

    def is_get_score(self, selected_ids):
        correct_choices = self.choice_set.filter(is_correct=True)

        selected_correct = correct_choices.filter(
            id__in=selected_ids
        ).count()

        return selected_correct == correct_choices.count()

    def __str__(self):
        return self.question_text


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=30)
    is_correct = models.BooleanField()

    def __str__(self):
        return self.choice_text


class Submission(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    choices = models.ManyToManyField(Choice)

    def __str__(self):
        return f"Submission {self.id} - {self.enrollment}"
