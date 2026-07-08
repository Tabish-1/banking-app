from django.urls import path
from conversionservice import views

urlpatterns = [
    path(
        'conversion/<str:currency1>/<str:currency2>/<str:amount>/',
        views.conversion_view,
        name='conversion'
    ),
]