from django.urls import include, path
from django.views.generic import RedirectView

# Django's own admin site is not enabled — see INSTALLED_APPS in settings.py.
# Administration lives at /webapps2026/admin/, served by payapp and register.
urlpatterns = [
    path('webapps2026/', include('register.urls')),
    path('webapps2026/', include('payapp.urls')),
    path('webapps2026/', include('conversionservice.urls')),

    # Entry points. Every page lives under a sub-path such as
    # /webapps2026/login/, so both the site root and the bare /webapps2026/
    # prefix used to return 404 — including the address the README tells people
    # to open. These send visitors to the dashboard, which in turn bounces
    # anonymous users to the login page.
    #
    # Declared after the includes: when the prefix matches but no sub-pattern
    # does, Django falls through to the next entry in this list.
    path('webapps2026/', RedirectView.as_view(pattern_name='dashboard')),
    path('', RedirectView.as_view(pattern_name='dashboard'), name='home'),
]
