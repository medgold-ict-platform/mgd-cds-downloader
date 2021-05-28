FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get -y install python3.7 && \
    apt-get -y install python3-pip && \
    apt-get -y install tzdata 
# Add these as a separate layer as they get updated frequently
RUN pip3 install awscli --force-reinstall --upgrade

COPY requirements.txt ./

RUN pip3 install -r ./requirements.txt

COPY .cdsapirc /root

COPY cds-era5.py ./

COPY run.sh ./

# RUN mkdir /opt/cdo-install
# COPY cdo-install/ /opt/cdo-install
# ENV PATH=/opt/cdo-install/bin:$PATH

RUN apt-get install -y cdo

ENV LD_LIBRARY_PATH /lib64:/usr/lib64:/var/runtime:/var/runtime/lib:/var/task:/var/task/lib:/opt/lib:/opt/pyt$
ENV username *******
ENV password *******
ENV login_url https://cds.climate.copernicus.eu/user/login?destination=/%23%21/home
ENV filesupdate_table dev-mgd-ict-platform-era5-cds-downloader-archive
ENV BUCKET_NAME  *******
ENV FIRST_BUCKET_PATH era5/raw/
ENV AWS_DEFAULT_REGION eu-west-1
ENV SECOND_BUCKET_PATH era5/p/

ENTRYPOINT ["/bin/sh"]

# CMD ["run.sh"]
