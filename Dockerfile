FROM mcr.microsoft.com/playwright/python:next-jammy-amd64



ENV DEBIAN_FRONTEND=noninteractive
RUN mkdir /config && mkdir /app && apt-get update && apt-get install -y tzdata && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
COPY . /app
RUN pip --no-cache-dir  install --user -r /app/requirements.txt
ADD https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64 /usr/local/bin/dumb-init
RUN chmod +x /usr/local/bin/dumb-init
WORKDIR /app
ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]
# -u print打印出来
CMD ["/bin/bash", "-c", "set -e && python3 -u pornbot.py"]
