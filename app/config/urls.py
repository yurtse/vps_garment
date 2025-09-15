from django.contrib import admin
from django.urls import path, include
#from django.views.generic import RedirectView
from django.shortcuts import redirect


urlpatterns = [
    # redirect root to admin
    #path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('home/', admin.site.urls),
    path("", lambda req: redirect("/home/")),   # simple redirect    
    # add other app urls below as you expand the project
    # path('app1/', include('app1.urls')),
]
