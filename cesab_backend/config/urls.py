from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('rosetta/', include('rosetta.urls')),
]

urlpatterns += i18n_patterns(
    path('auth/', include('auth_users.urls', namespace='auth_users')),
    path('projects/', include('projects.urls', namespace='projects')),
    prefix_default_language=False,
)

urlpatterns += [path('', RedirectView.as_view(url='/projects/', permanent=False))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
