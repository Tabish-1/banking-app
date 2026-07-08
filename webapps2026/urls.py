from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webapps2026/', include('register.urls')),
    path('webapps2026/', include('payapp.urls')),
    path('webapps2026/', include('conversionservice.urls')),
]