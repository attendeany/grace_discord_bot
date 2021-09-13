# set base image
FROM python:3.9-slim-buster

# working dir
WORKDIR /container

# discord.py dependencies
RUN python -m pip install --upgrade pip && pip install --no-cache-dir aiohttp

# discord.py v2.0
RUN apt update && apt install -y git && \
 git clone https://github.com/Rapptz/discord.py discordpy && \
 ln -sfn discordpy/discord discord && \
 apt remove -y git

# copy bot source code
COPY echo_bot echo_bot

# copy main source file
COPY main.py .

# run command
ENTRYPOINT ["python", "main.py"]
