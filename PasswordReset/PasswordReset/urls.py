from django.urls import include, path

urlpatterns = [
    path('reset/', include('app.urls')),
]
