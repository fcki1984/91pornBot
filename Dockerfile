FROM ubuntu:jammy
MAINTAINER jwstar
ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir /config  \
    && mkdir /app && apt-get -y update  \
    && apt-get install -y python3.10 python3-pip python3.10-dev ffmpeg  tzdata  \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    # 用完包管理器后安排打扫卫生可以显著的减少镜像大小
    && apt-get clean \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . /app

RUN pip --no-cache-dir  install --user -r /app/requirements.txt  \
    && python3.10 -m playwright install chromium --with-deps

ADD https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64 /usr/local/bin/dumb-init
RUN chmod +x /usr/local/bin/dumb-init

WORKDIR /app
ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]
CMD ["/bin/bash", "-c", "set -e && python3.10 -u pornbot.py"]