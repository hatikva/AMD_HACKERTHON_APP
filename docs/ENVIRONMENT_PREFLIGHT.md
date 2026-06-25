# Environment Preflight

Observed on 2026-06-25 before initial scaffold.

```text
kernel: Linux PANSLA 6.6.87.2-microsoft-standard-WSL2 x86_64
pid_1: systemd
cpu_count: 8
memory: 11Gi total, 10Gi available
disk: 1007G total, 685G available at repository path
container_cli: podman version 5.8.1 exposed through docker command
compose_provider: podman-compose version 1.5.0
ollama_command: /usr/local/bin/ollama
lemonade_command: not found on host
port_11434: listening on 127.0.0.1
port_13305: not observed listening
```

Implication: local Lemonade runtime verification is pending. The development files are Compose-compatible, but the current environment is Podman-backed rather than Docker Desktop-backed.
