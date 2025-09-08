from django.urls import re_path, include
from django.views.generic import RedirectView
from django.contrib.auth.decorators import user_passes_test
from django.utils.http import urlencode

from django.shortcuts import redirect
from django.contrib import admin
from lucosauth import views as auth_views
from agents import views as agents_views
from agents import calendar as calendar_views
admin.autodiscover()

"""Send all admin login attempts straight to /accounts/login."""
def direct_admin_login(request, extra_context=None):
    params = urlencode({"next": request.GET.get("next", "/admin/")})
    return redirect(f"/accounts/login/?{params}")

admin.site.login = direct_admin_login

urlpatterns = [
	re_path(r'^people/(?P<extid>(\d+|me|add))(/(?P<method>(view|accounts|starred)))?/?$', agents_views.agent),
	re_path(r'^people/(?P<list>(phone|postal|gifts|starred|all))$', agents_views.agentindex),
	re_path(r'^calendar/?$', calendar_views.renderCalendar),
	re_path(r'^calendar.ics$', calendar_views.outputICalendar),
	re_path(r'^people/import$', agents_views.importer),
	re_path(r'^identify/?$', agents_views.identify),
	re_path(r'^(?:people/?)?$', RedirectView.as_view(url='/people/starred')),
	# Static files (icons, bootloader) are handled by nginx

	# Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
	# to INSTALLED_APPS to enable admin documentation:
	# url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

	re_path(r'^admin/', admin.site.urls),
	re_path(r'^accounts/login/', auth_views.loginview),
	re_path(r'^_info$', agents_views.info),
	re_path (r'^i18n/' ,include('django.conf.urls.i18n')),

	re_path(r'^agents/(?P<subpath>.*)', RedirectView.as_view(url='/people/%(subpath)s', permanent=True)),
]
