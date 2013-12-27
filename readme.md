#lucos Contacts
A list of contacts

## Dependencies
* django
* A database (and the relevant python libraries to use that database

## Setup
A file called local_settings.py needs to be added to the root of the project.  It should include:
* standard django [DATABASE settings](https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-DATABASES)
* A variable called API_KEY used by other applications wanting to use the contacts API
* A variable called AUTH_DOMAIN to indicate where to authenticate against

## Running
The web server is designed to be run within lucos_services, but can be run standalone (see django documentation for details)

## Language support
Some fields support having values in different languages.  Currently this is limited to:
* English
* Irish
* Scottish Gaelic
* Welsh
These are hardcoded values, so can only be change by make source code changes in several places.  Obviously this isn't very scabable, but a scalable solution would require a more complicated database schema and I wasn't sure if there was enough demand for this.
