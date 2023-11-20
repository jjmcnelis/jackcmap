FROM ghcr.io/osgeo/gdal:alpine-normal-latest

RUN apk add build-base

#RUN echo "http://dl-8.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
#RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
RUN echo "https://dl-cdn.alpinelinux.org/alpine/latest-stable/community" >> /etc/apk/repositories \
  && apk update \
  && apk add py3-pip py3-numpy py3-pandas py3-kiwisolver

RUN pip3 install matplotlib bokeh

VOLUME '/app'

EXPOSE 5006

ENTRYPOINT ["python", "/app/jackcmap.py", "/app/test.tif"]
