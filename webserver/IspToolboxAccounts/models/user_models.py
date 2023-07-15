# from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.hashers import make_password
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import UserManager
from django.contrib.sessions.models import Session
from django.contrib.postgres.fields import ArrayField

from webserver.celery import celery_app as app


class IspToolboxUserManager(UserManager):
    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError("User must have an email")
        if not password:
            raise ValueError("User must have a password")
        if not first_name:
            raise ValueError("User must have a first name")
        if not last_name:
            raise ValueError("User must have a last name")

        user = self.model(
            email=self.normalize_email(email)
        )
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(password)
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

    def create_user(self, email, first_name, last_name, password=None):
        """
        Creates and saves a User with the given email, first & last name and
        password
        """
        if not email:
            raise ValueError('Users must have an email address')
        if not password:
            raise ValueError("User must have a password")
        if not first_name:
            raise ValueError("User must have a first name")
        if not last_name:
            raise ValueError("User must have a last name")

        user = self.model(
            email=self.normalize_email(email),
            first_name=first_name,
            last_name=last_name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    objects = IspToolboxUserManager()

    class Meta(AbstractUser.Meta):
        db_table = 'auth_user'
        swappable = 'AUTH_USER_MODEL'


class IspToolboxUserSignUpInfo(models.Model):
    SUBSCRIBER_SIZE_CHOICES = (
        ("", _("Choose subscriber size")),
        ("aspiring", _("I don\'t service anyone right now")),
        ("small", _("1 - 100")),
        ("medium", _("101 - 500")),
        ("large", _("501 - 2,000")),
        ("xlarge", _("2,001 - 5,000")),
        ("xxlarge", _("5,000+")),
    )
    BUSINESS_TYPES = (
        ("wireless", _("Wireless")),
        ("coax", _("Coax")),
        ("fiber", _("Fiber")),
    )
    ROLE_CHOICES = (
        ("bus_fin", _("Business & Finance")),
        ("tech_install", _("Tech & Installation")),
        ("mar_sales", _("Marketing & Sales")),
    )
    GOAL_CHOICES = (
        ("start_business", _("Start an ISP Business")),
        ("customer_acquistion", _("Acquire more customers")),
        ("expansion", _("Expand service to new areas")),
    )

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company_website = models.CharField(max_length=100, null=True)
    subscriber_size = models.CharField(
        null=True,
        max_length=50,
    )

    business_type = ArrayField(models.CharField(
        max_length=128,
        choices=BUSINESS_TYPES,
    ))
    individual_role = ArrayField(models.CharField(
        max_length=128,
        choices=ROLE_CHOICES,
    ))
    company_goal = ArrayField(models.CharField(
        max_length=128,
        choices=GOAL_CHOICES,
    ))


class NewUserExperience(models.Model):
    name = models.CharField(
        max_length=50, unique=True,
        help_text="""Name of the new user experience - used for template tags. Must be unique""")
    description = models.CharField(
        max_length=255, blank=True, help_text="""Description of what the nux does""")
    users = models.ManyToManyField(
        to=settings.AUTH_USER_MODEL, blank=True, help_text="""Users that have seen the nux""")
    anonymous_sessions = models.ManyToManyField(
        to=Session, blank=True, help_text="""Anonymous Users - cookie based sessions"""
    )

    @property
    def num_users_seen(self):
        return self.users.count()

    @property
    def num_anonymous_users_seen(self):
        return self.anonymous_sessions.count()


class PageVisit(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True
    )
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, blank=True, null=True
    )
    request = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    response_code = models.IntegerField(
        blank=True, null=True
    )
    ip = models.GenericIPAddressField(
        blank=True, null=True, db_index=True
    )
