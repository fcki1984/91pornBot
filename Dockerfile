FROM ubuntu:jammy
MAINTAINER jwstar
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir /config  \
    && mkdir /app && apt-get -y update  \
    && apt-get install -y wget python3.10 python3-pip python3.10-dev \
    #安装amd64 ffmpeg二进制
    && wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar xvf ffmpeg-*.tar.xz \
    && mv  ffmpeg-*/ffmpeg /usr/bin/ \
    && rm -rf ffmpeg-* \
    # 用完包管理器后安排打扫卫生可以显著的减少镜像大小 \
    && apt-get remove -y wget --purge  \
    && apt-get clean \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . /app

RUN pip --no-cache-dir  install --user -r /app/requirements.txt  \
    && python3.10 -m playwright install chromium --with-deps

WORKDIR /app

CMD ["/bin/bash", "-c", "set -e && python3.10 -u pornbot.py"]