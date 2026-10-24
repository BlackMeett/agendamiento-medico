from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("cuenta/", include("accounts.urls")),
    path("gestion/", include("gestion.urls")),
    path("portal/", include("portal.urls")),
]
