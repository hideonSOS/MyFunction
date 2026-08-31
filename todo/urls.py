from django.urls import path

from . import views

app_name = 'todo'

urlpatterns = [
    path('',                    views.index,             name='index'),
    path('api/list/',           views.api_list,          name='api_list'),
    path('api/save/',           views.api_save,          name='api_save'),
    path('api/delete/',         views.api_delete,        name='api_delete'),
    path('api/reorder/',        views.api_reorder,       name='api_reorder'),
    path('api/upload/',         views.api_upload,        name='api_upload'),
    path('api/attach/delete/',  views.api_attach_delete, name='api_attach_delete'),
    path('api/attach/reorder/', views.api_attach_reorder, name='api_attach_reorder'),
]
