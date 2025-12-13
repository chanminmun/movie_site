"""
URL configuration for movies project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path,include
from msite import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('browse/', views.browse, name='browse'),
    path('guess/', views.guess, name='guess'),
    path('streams/', views.streams, name='streams'),
    path('movies/', views.movie_list, name='movie_list'),
    path('movies/<int:tmdb_id>/', views.movie_detail, name='movie_detail'),
    path('accounts/', include('allauth.urls')),
    path("comment/<int:comment_id>/delete/", views.comment_delete, name="comment_delete"),
    path("movies/<int:tmdb_id>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("search/", views.search, name="search"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)