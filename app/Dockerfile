FROM node:25-alpine AS ui-builder

WORKDIR /build
COPY package* ./

RUN npm ci

FROM python:3.15.0a8-alpine
ARG VERSION
ENV VERSION=$VERSION

# set working directory
WORKDIR /usr/src/app

# set environment varibles
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install apk dependencies
RUN apk update
RUN apk add postgresql-dev # Needed for database connection
RUN apk add gettext # Needed for translations

# Install pip dependencies
RUN apk add --virtual build-deps gcc python3-dev musl-dev # These are needed to install pyscopg, but can be removed after
COPY Pipfile* .
RUN pip install --upgrade pip pipenv
RUN pipenv install --system
RUN apk del build-deps gcc python3-dev musl-dev

# Copy project after dependencies, so cached dependencies can be used if unchanged
COPY . .
COPY --from=ui-builder /build/node_modules/lucos_navbar/lucos_navbar.js templates/resources/

# Compile Translations
RUN django-admin compilemessages

# Collect static files at build time so startup.sh doesn't need to.
# Uses a minimal settings file that only declares what collectstatic needs,
# avoiding the env var requirements of the full settings module.
RUN python manage.py collectstatic --noinput --settings=settings_collectstatic

CMD ["./startup.sh"]