FROM python:2.7-alpine

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

# copy project
COPY . /usr/src/app/

# install dependencies
RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install --skip-lock --system


CMD ["./startup.sh"]