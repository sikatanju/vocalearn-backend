from django.urls import path

from . import views

urlpatterns = [
    path('hello/', views.hello, name='hello'),
    path("translate/", views.translate_text_view, name='translate_text')
]
