from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
import logging

from .models import (
    Course,
    Lesson,
    Enrollment,
    Question,
    Choice,
    Submission,
    Instructor,
    Learner,
)

# Get an instance of a logger
logger = logging.getLogger(__name__)


# -------------------------
# User registration
# -------------------------

def registration_request(request):
    context = {}

    if request.method == "GET":
        return render(
            request,
            "onlinecourse/user_registration_bootstrap.html",
            context
        )

    elif request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("psw")
        first_name = request.POST.get("firstname")
        last_name = request.POST.get("lastname")

        user_exist = User.objects.filter(username=username).exists()

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )

            login(request, user)
            return redirect("onlinecourse:index")

        context["message"] = "User already exists."

        return render(
            request,
            "onlinecourse/user_registration_bootstrap.html",
            context
        )


# -------------------------
# User login
# -------------------------

def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("psw")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("onlinecourse:index")

        context["message"] = "Invalid username or password."

        return render(
            request,
            "onlinecourse/user_login_bootstrap.html",
            context
        )

    return render(
        request,
        "onlinecourse/user_login_bootstrap.html",
        context
    )


# -------------------------
# User logout
# -------------------------

def logout_request(request):
    logout(request)
    return redirect("onlinecourse:index")


# -------------------------
# Enrollment helper
# -------------------------

def check_if_enrolled(user, course):
    if not user.is_authenticated:
        return False

    return Enrollment.objects.filter(
        user=user,
        course=course
    ).exists()


# -------------------------
# Course list
# -------------------------

class CourseListView(generic.ListView):
    template_name = "onlinecourse/course_list_bootstrap.html"
    context_object_name = "course_list"

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by("-total_enrollment")[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


# -------------------------
# Course details
# -------------------------

class CourseDetailView(generic.DetailView):
    model = Course
    template_name = "onlinecourse/course_detail_bootstrap.html"


# -------------------------
# Enroll in a course
# -------------------------

def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if user.is_authenticated:
        is_enrolled = check_if_enrolled(user, course)

        if not is_enrolled:
            Enrollment.objects.create(
                user=user,
                course=course,
                mode="honor"
            )

            course.total_enrollment += 1
            course.save()

    return HttpResponseRedirect(
        reverse(
            viewname="onlinecourse:course_details",
            args=(course.id,)
        )
    )


# -------------------------
# Extract selected answers
# -------------------------

def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        # Supports form fields named choice, choices, choice_1, etc.
        if key.startswith("choice"):
            values = request.POST.getlist(key)

            for value in values:
                try:
                    submitted_answers.append(int(value))
                except (TypeError, ValueError):
                    continue

    # Remove duplicate IDs while preserving order
    return list(dict.fromkeys(submitted_answers))


# -------------------------
# Submit exam
# -------------------------

def submit(request, course_id):
    if request.method != "POST":
        return redirect(
            "onlinecourse:course_details",
            course_id=course_id
        )

    if not request.user.is_authenticated:
        return redirect("onlinecourse:login")

    course = get_object_or_404(Course, id=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    selected_choice_ids = extract_answers(request)

    for choice_id in selected_choice_ids:
        choice = get_object_or_404(
            Choice,
            id=choice_id
        )

        # Make sure the choice belongs to a question in this course
        if choice.question.lesson.course_id == course.id:
            submission.choices.add(choice)

    return HttpResponseRedirect(
        reverse(
            viewname="onlinecourse:show_exam_result",
            args=(course.id, submission.id)
        )
    )


# -------------------------
# Show exam result
# -------------------------

def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect("onlinecourse:login")

    course = get_object_or_404(
        Course,
        id=course_id
    )

    submission = get_object_or_404(
        Submission,
        id=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    selected_choices = submission.choices.all()

    questions = Question.objects.filter(
        lesson__course=course
    ).distinct()

    total_score = 0
    max_score = 0
    exam_results = []

    for question in questions:
        question_mark = question.mark
        max_score += question_mark

        correct_choices = question.choice_set.filter(
            is_correct=True
        )

        selected_for_question = selected_choices.filter(
            question=question
        )

        correct_choice_ids = set(
            correct_choices.values_list("id", flat=True)
        )

        selected_choice_ids = set(
            selected_for_question.values_list("id", flat=True)
        )

        # The answer is correct only when all correct choices
        # and only those choices have been selected.
        is_correct = (
            correct_choice_ids == selected_choice_ids
        )

        earned_mark = question_mark if is_correct else 0
        total_score += earned_mark

        exam_results.append({
            "question": question,
            "selected_choices": selected_for_question,
            "correct_choices": correct_choices,
            "is_correct": is_correct,
            "mark": earned_mark,
            "possible_mark": question_mark,
        })

    if max_score > 0:
        grade = round((total_score / max_score) * 100)
    else:
        grade = 0

    passed = grade >= 70

    context = {
        "course": course,
        "submission": submission,

        # Detailed results
        "exam_results": exam_results,

        # Score values
        "total_score": total_score,
        "max_score": max_score,
        "grade": grade,
        "percentage": grade,
        "passed": passed,

        # Selected choices, also available for templates
        "selected_choices": selected_choices,
        "selected_ids": selected_choices,
    }

    return render(
        request,
        "onlinecourse/exam_result_bootstrap.html",
        context
    )
