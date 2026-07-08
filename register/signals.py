from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_initial_admin(sender, **kwargs):
    if sender.name != 'register':
        return

    from django.contrib.auth.models import User
    from register.models import UserProfile

    if not User.objects.filter(username='admin1').exists():
        admin_user = User.objects.create_user(
            username='admin1',
            password='admin1',
            first_name='Admin',
            last_name='User',
            email='admin1@webapps2026.com',
        )
        UserProfile.objects.create(
            user=admin_user,
            currency='GBP',
            balance=0.00,
            is_admin=True,
        )