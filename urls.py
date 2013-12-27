from django.conf.urls import patterns, url, include
from django.views.generic import RedirectView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^contacts/', include('contacts.foo.urls')),
     (r'^agents/(?P<extid>(\d+|me|add))(/(?P<method>(edit|view|accounts)))?/?$', 'agents.views.agent'),
     (r'^agents/(?P<list>(phone|postal|all))$', 'agents.views.agentindex'),
     (r'^identify/?$', 'agents.views.identify'),
     (r'^resources$', 'agents.views.resources'),
     (r'^(?:agents/?)?$', RedirectView.as_view(url='/agents/all')),
     (r'^favicon.ico$', 'django.views.static.serve', {'document_root': 'templates/resources/', 'path': 'favicon.png'}),
     (r'^icon$', 'django.views.static.serve', {'document_root': 'templates/resources/', 'path': 'logo.png'}),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
     (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
     (r'^admin/', include(admin.site.urls)),
)
