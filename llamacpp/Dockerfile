FROM debian:bookworm-slim

RUN apt-get update && apt-get install --yes --no-install-recommends curl libgomp1 && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["bash", "/llamacpp/llamacpp-linux/start-llama.sh"]
