from django.urls import path
from . import views

app_name = 'mailfunction'

urlpatterns = [
    path('',                                        views.index,               name='index'),
    path('fetch/',                                  views.fetch_mails,         name='fetch_mails'),
    path('log/',                                    views.log_view,            name='log_view'),
    path('search/',                                 views.search,              name='search'),
    path('detail/<str:mail_id>/',                   views.mail_detail,         name='mail_detail'),
    path('attachment/<str:mail_id>/<str:attachment_id>/', views.attachment_download, name='attachment_download'),
    path('contacts/',                               views.contacts,            name='contacts'),
    path('send/',                                   views.send_mail,           name='send_mail'),
    path('oauth/start/',                            views.oauth_start,         name='oauth_start'),
    path('oauth/callback/',                         views.oauth_callback,      name='oauth_callback'),
]
