from django.urls import path
from payapp import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('send/', views.send_payment_view, name='send_payment'),
    path('request/', views.request_payment_view, name='request_payment'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('handle-request/<int:pk>/', views.handle_payment_request_view, name='handle_request'),
    
    # Admin URLs
    path('admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/transactions/', views.admin_transactions_view, name='admin_transactions'),
    path('admin/users/', views.admin_users_view, name='admin_users'),
    
    # Notification mark as read URLs (AJAX support)
    path('mark-notification-read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-notifications-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]