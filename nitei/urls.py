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
    path('e/',                  views.schedule, {'person': 'e'},  name='schedule_e'),
    path('f/',                  views.schedule, {'person': 'f'},  name='schedule_f'),
    path('g/',                  views.schedule, {'person': 'g'},  name='schedule_g'),
    path('h/',                  views.schedule, {'person': 'h'},  name='schedule_h'),
    path('i/',                  views.schedule, {'person': 'i'},  name='schedule_i'),
    path('j/',                  views.schedule, {'person': 'j'},  name='schedule_j'),
    path('k/',                  views.schedule, {'person': 'k'},  name='schedule_k'),
    path('l/',                  views.schedule, {'person': 'l'},  name='schedule_l'),
    path('overview/',             views.overview,                   name='overview'),
    path('api/overview/',         views.api_overview,               name='api_overview'),
    path('api/titles/',           views.api_titles,                 name='api_titles'),
    path('api/schedule/',       views.api_schedule,               name='api_schedule'),
    path('api/schedule/save/',  views.api_schedule_save,          name='api_schedule_save'),
    path('api/schedule/clear/', views.api_schedule_clear,         name='api_schedule_clear'),
    path('api/events/',         views.api_events,                 name='api_events'),
    path('api/events/save/',    views.api_events_save,            name='api_events_save'),
]
