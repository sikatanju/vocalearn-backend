from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path("translate/", views.translate_text_view, name='translate_text'),
    path("speech/", views.speech_to_text_view, name="speech-to-text"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)