from django.urls import path
from . import views

urlpatterns = [
    path('',             views.index,           name='index'),
    path('fetch/',       views.fetch_docs,       name='fetch_docs'),
    path('run/',         views.run_copy,         name='run_copy'),
    path('log/',         views.log_view,         name='log'),
    path('kaisai_data/', views.kaisai_data_view, name='kaisai_data'),
]
