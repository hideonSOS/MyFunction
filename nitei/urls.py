from django.urls import path
from . import views

app_name = 'nitei'

urlpatterns = [
    path('login/',              views.nitei_login,                name='login'),
    path('logout/',             views.nitei_logout,               name='logout'),
    path('',                    views.top,                        name='top'),
    path('a/',                  views.schedule, {'person': 'a'},  name='schedule_a'),
    path('b/',                  views.schedule, {'person': 'b'},  name='schedule_b'),
    path('c/',                  views.schedule, {'person': 'c'},  name='schedule_c'),
    path('d/',                  views.schedule, {'person': 'd'},  name='schedule_d'),
    path('api/titles/',         views.api_titles,                 name='api_titles'),
    path('api/schedule/',       views.api_schedule,               name='api_schedule'),
    path('api/schedule/save/',  views.api_schedule_save,          name='api_schedule_save'),
    path('api/schedule/clear/', views.api_schedule_clear,         name='api_schedule_clear'),
    path('api/events/',         views.api_events,                 name='api_events'),
    path('api/events/save/',    views.api_events_save,            name='api_events_save'),
]
