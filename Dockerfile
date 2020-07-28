# [*] First build image with:
#
# sudo docker build --tag mistica:latest .
#
# [*] Second, create the network with:
#
# sudo docker network create misticanw
#
# [*] Third run the server with (BEWARE of the volume, change the path to this directory):
#
# sudo docker run --network misticanw --sysctl net.ipv4.icmp_echo_ignore_all=1 -v $(pwd):/opt/Mistica -it mistica /bin/bash
#
# [*] Fourth run the client with (BEWARE of the volume, change the path to this directory):
#
# sudo docker run --network misticanw -v $(pwd):/opt/Mistica -it mistica /bin/bash

FROM python:3.7

LABEL maintainer="rcaro@incide.es"

RUN python3.7 -m pip install pip && python3.7 -m pip install dnslib

WORKDIR /opt/Mistica

ENTRYPOINT /bin/bash

