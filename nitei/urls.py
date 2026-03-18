from django.urls import path
from . import views

app_name = 'nitei'

urlpatterns = [
    path('',                    views.index,              name='index'),
    path('api/titles/',         views.api_titles,         name='api_titles'),
    path('api/schedule/',       views.api_schedule,       name='api_schedule'),
    path('api/schedule/save/',  views.api_schedule_save,  name='api_schedule_save'),
    path('api/schedule/clear/', views.api_schedule_clear, name='api_schedule_clear'),
]
