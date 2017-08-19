from django.conf.urls import url
from . import views
from views import *

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^gettoken/$', GetToken.as_view(), name='gettoken'),
    url(r'^setpassword/$', SetPassword.as_view(), name='setpassword'),
]
