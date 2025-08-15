from django.urls import path
from .views import download_video

urlpatterns = [
    path('download/', download_video, name='download-video'),
    
]
