from django.urls import path

from . import views

app_name = 'fusen'

urlpatterns = [
    path('',                    views.board,             name='board'),
    path('api/state/',          views.api_state,         name='api_state'),

    path('api/note/save/',      views.api_note_save,     name='api_note_save'),
    path('api/note/delete/',    views.api_note_delete,   name='api_note_delete'),

    path('api/task/save/',      views.api_task_save,     name='api_task_save'),
    path('api/task/status/',    views.api_task_status,   name='api_task_status'),
    path('api/task/reminded/',  views.api_task_reminded, name='api_task_reminded'),
    path('api/task/delete/',    views.api_task_delete,   name='api_task_delete'),
]
