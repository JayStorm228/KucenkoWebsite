from django.shortcuts import get_object_or_404, render

from .models import Course


def index(request):
    courses = Course.objects.all()
    context = {"courses": courses}
    return render(request, "shop/courses.html", context)


def single_course(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    context = {"course": course}
    return render(request, "shop/single_course.html", context)


def page_not_found(request, exception):
    return render(
        request,
        "shop/includes/404.html",
        status=404,
    )
