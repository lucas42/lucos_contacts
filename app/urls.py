from django.urls import re_path, include
from django.views.generic import RedirectView
from django.contrib.auth.decorators import user_passes_test

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from lucosauth import views as auth_views
from agents import views as agents_views
from agents import calendar as calendar_views
admin.autodiscover()
admin.site.login = user_passes_test(lambda u:u.is_staff, login_url='/accounts/login/')(admin.site.login)

urlpatterns = [
	re_path(r'^agents/(?P<extid>(\d+|me|add))(/(?P<method>(view|accounts|starred)))?/?$', agents_views.agent),
	re_path(r'^agents/(?P<list>(phone|postal|gifts|starred|all))$', agents_views.agentindex),
	re_path(r'^calendar/?$', calendar_views.renderCalendar),
	re_path(r'^calendar.ics$', calendar_views.outputICalendar),
	re_path(r'^agents/import$', agents_views.importer),
	re_path(r'^identify/?$', agents_views.identify),
	re_path(r'^(?:agents/?)?$', RedirectView.as_view(url='/agents/starred')),
	# Static files (icons, bootloader) are handled by nginx

	# Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
	# to INSTALLED_APPS to enable admin documentation:
	# url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

	re_path(r'^admin/', admin.site.urls),
	re_path(r'^accounts/login/', auth_views.loginview),
	re_path(r'^_info$', agents_views.info),
	re_path (r'^i18n/' ,include('django.conf.urls.i18n')),
]
