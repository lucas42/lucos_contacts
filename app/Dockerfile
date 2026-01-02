FROM node:25-alpine AS ui-builder

WORKDIR /build
COPY package* ./

RUN npm ci

FROM python:3.15.0a3-alpine

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
COPY --from=ui-builder /build/node_modules/tom-select/dist/js/tom-select.complete.js templates/resources/
COPY --from=ui-builder /build/node_modules/tom-select/dist/css/tom-select.default.css templates/resources/

# Compile Translations
RUN django-admin compilemessages

CMD ["./startup.sh"]