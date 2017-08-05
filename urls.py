from django.conf.urls import url, include
from django.views.generic import RedirectView
from django.contrib.auth.decorators import user_passes_test

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from lucosauth import views as auth_views
from agents import views as agents_views
admin.autodiscover()
admin.site.login = user_passes_test(lambda u:u.is_staff, login_url='/accounts/login/')(admin.site.login)

urlpatterns = [
    # Example:
    # (r'^contacts/', include('contacts.foo.urls')),
    url(r'^agents/(?P<extid>(\d+|me|add))(/(?P<method>(edit|view|accounts)))?/?$', agents_views.agent),
    url(r'^agents/(?P<list>(phone|postal|all))$', agents_views.agentindex),
    url(r'^identify/?$', agents_views.identify),
    url(r'^resources$', agents_views.resources),
    url(r'^(?:agents/?)?$', RedirectView.as_view(url='/agents/all')),
	# Static files (icons, bootloader) are handled directly in apache using aliases

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
#    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    url(r'^admin/$', RedirectView.as_view(url='/agents/all')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/login/', auth_views.loginview),
]
