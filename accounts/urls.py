from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('sign_up/', views.sign_up, name='sign_up'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]