FROM lucas42/lucos_navbar:latest as navbar
FROM python:3.11.4-alpine

# set work directory
WORKDIR /usr/src/app

# set environment varibles
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2
RUN apk update \
    && apk add --virtual build-deps gcc python3-dev musl-dev \
    && apk add postgresql-dev \
    && pip install psycopg2 \
    && apk del build-deps

# Needed for translations
RUN apk add gettext

# Install dependencies
COPY Pipfile .
RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install --skip-lock --system

# Copy project after dependencies, so cached dependencies can be used if unchanged
COPY . .
COPY --from=navbar lucos_navbar.js templates/resources/

# Compile Translations
RUN django-admin compilemessages

CMD ["./startup.sh"]