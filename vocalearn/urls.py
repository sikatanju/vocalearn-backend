from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path("translate/", views.translate_text_view, name='translate_text'),
    path("speech/", views.speech_to_text_view, name="speech-to-text"),
    path('pronunciation/', views.pronunciation_assesment_view, name='pronunciation-assesment'),
    
    # Saved items management
    path('saved-items/', views.get_saved_items, name='get_saved_items'),
    path('saved-items/<uuid:item_id>/', views.delete_saved_item, name='delete_saved_item'),
    path('saved-items/<uuid:item_id>/audio/', views.download_audio, name='download_audio'),
    
    # Collections management
    path('saved-items/<uuid:item_id>/collections/', views.add_item_to_collection, name='add_item_to_collection'),
    path('saved-items/<uuid:item_id>/collections/<uuid:collection_id>/', views.remove_item_from_collection, name='remove_item_from_collection'),
    
    # User quota
    path('quota/', views.get_user_quota, name='get_user_quota'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)