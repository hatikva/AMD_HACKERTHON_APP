FROM ghcr.io/lemonade-sdk/lemonade-server:v9.1.3

COPY containers/lemonade/defaults.json /opt/amd-hackathon/lemonade-defaults.json

EXPOSE 13305

CMD ["./lemond", "--host", "0.0.0.0", "--port", "13305"]
