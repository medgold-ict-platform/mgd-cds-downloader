#!/bin/bash

mkdir /opt/cdo-install
home=/opt/cdo-install 

sudo su

yum install -y wget
# yum install gcc
# yum install gcc-c++
# yum install m4
#   download, compile and install --> zlib
cd $home
wget ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-4/zlib-1.2.8.tar.gz
tar -xzvf zlib-1.2.8.tar.gz
cd zlib-1.2.8
./configure -prefix=/opt/cdo-install 
make && make check && make install

#   download, compile and install --> hdf5
cd /opt/cdo-install 
wget ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-4/hdf5-1.8.13.tar.gz
tar -xzvf hdf5-1.8.13.tar.gz
cd hdf5-1.8.13
./configure -with-zlib=/opt/cdo-install -prefix=/opt/cdo-install CFLAGS=-fPIC
make && make check && make install

#   download, compile and install --> netCDF
cd /opt/cdo-install 
wget ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-cxx-4.2.tar.gz
tar -xzvf netcdf-cxx-4.2.tar.gz
cd netcdf-cxx-4.2/
CPPFLAGS=-I/opt/cdo-install/include LDFLAGS=-L/opt/cdo-install/lib ./configure -prefix=/opt/cdo-install CFLAGS=-fPIC
make && make check && make install
http://www.unidata.ucar.edu/downloads/netcdf/ftp/netcdf-4.1.3
#   download, compile and install --> jasper
# cd $home
# wget http://www.ece.uvic.ca/~frodo/jasper/software/jasper-1.900.1.zip
# unzip jasper-1.900.1.zip
# cd jasper-1.900.1
# ./configure -prefix=./ CFLAGS=-fPIC
# make && make check && make install

#   download, compile and install --> grib_api
cd /opt/cdo-install 
wget -OL https://software.ecmwf.int/wiki/download/attachments/3473437/grib_api-1.24.0-Source.tar.gz?api=v2 grib_api-1.24.0.tar.gz
tar -xzvf grib_api-1.24.0.tar.gz
cd grib_api-1.24.0-Source
./configure -prefix=/opt/cdo-install CFLAGS=-fPIC -with-netcdf=/opt/cdo-install -with-jasper=/opt/cdo-install
make && make check && make install

#   download, compile and install --> cdo
cd /opt/cdo-install 
wget https://code.mpimet.mpg.de/attachments/download/15653/cdo-1.9.1.tar.gz
tar -xvzf cdo-1.9.1.tar.gz
cd cdo-1.9.1
./configure -prefix=/opt/cdo-install CFLAGS=-fPIC -with-netcdf=./opt/cdo-install -with-hdf5=./opt/cdo-install
make && make check && make install

#   set PATH
echo "PATH=\"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games::/snap/bin:/opt/cdo-install\""