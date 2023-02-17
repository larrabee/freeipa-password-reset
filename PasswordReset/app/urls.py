from django.urls import path

from . import views
from .views import *

urlpatterns = [
    path('', views.index, name='index'),
    path('gettoken/', GetToken.as_view(), name='gettoken'),
    path('setpassword/', SetPassword.as_view(), name='setpassword'),
]
