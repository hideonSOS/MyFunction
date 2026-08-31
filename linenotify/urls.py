from django.urls import path

from . import views

app_name = 'linenotify'

urlpatterns = [
    path('',                   views.index,             name='index'),
    path('api/list/',          views.api_list,          name='api_list'),
    path('api/save/',          views.api_save,          name='api_save'),
    path('api/delete/',        views.api_delete,        name='api_delete'),
    path('api/sendnow/',       views.api_send_now,      name='api_send_now'),
    path('api/test/',          views.api_test,          name='api_test'),
    path('api/target/save/',   views.api_target_save,   name='api_target_save'),
    path('webhook/',           views.webhook,           name='webhook'),
]
