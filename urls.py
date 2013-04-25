from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^contacts/', include('contacts.foo.urls')),
     (r'^agents/(?P<extid>(\d+|me|add))(/(?P<method>(edit|view|accounts)))?/?$', 'contacts.agents.views.agent'),
     (r'^agents/(?P<list>(phone|postal|all))$', 'contacts.agents.views.agentindex'),
     (r'^identify/?$', 'contacts.agents.views.identify'),
     (r'^resources$', 'contacts.agents.views.resources'),
     (r'^(?:agents/?)?$', redirect_to, {'url': '/agents/all'}),
     (r'^favicon.ico$', 'django.views.static.serve', {'document_root': 'templates/resources/', 'path': 'favicon.png'}),
     (r'^icon$', 'django.views.static.serve', {'document_root': 'templates/resources/', 'path': 'logo.png'}),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
     (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
     (r'^admin/', include(admin.site.urls)),
)
