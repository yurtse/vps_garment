from django.contrib import admin
from django.urls import path, include
#from django.views.generic import RedirectView
from django.shortcuts import redirect
from . import views


urlpatterns = [
    path("api/autocomplete/fg/", views.fg_autocomplete, name="fg_autocomplete"),
    path("api/autocomplete/components/", views.components_autocomplete, name="components_autocomplete"),
 
]
