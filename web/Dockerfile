FROM nginx:1.29.4-alpine3.23
ARG VERSION
ENV VERSION=$VERSION

RUN rm /etc/nginx/conf.d/*
RUN rm /usr/share/nginx/html/*

COPY routing.conf /etc/nginx/conf.d/
COPY --from=app /usr/src/app/static /usr/share/nginx/html/resources

CMD ["nginx", "-g", "daemon off;"]
