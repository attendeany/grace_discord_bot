# Grace bot

### Build docker image
```shell
docker build -t grace-bot:latest .
```

### Deploy docker container
```shell
docker run <data-path>:/container/data -e "token=<bot-token>" grace-bot:latest
```
