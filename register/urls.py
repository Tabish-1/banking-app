from django.urls import path
from register import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/register-admin/', views.admin_register_view, name='admin_register'),
]