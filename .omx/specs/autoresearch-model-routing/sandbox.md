# Sandbox

- Writable scope: `config/litellm.yaml`, `evals/model-routing/`, this autoresearch
  scope, and the config contract test required by candidate aliases.
- Stable product aliases and all application/UI code remain unchanged.
- Gateway calls target `http://127.0.0.1:4000/v1` by default and run sequentially.
- The runner never prints or persists the gateway/API key, request headers, image
  bytes, data URLs, or raw provider objects.
- Seedream/image generation is not invoked.
- Result JSON is sanitized and may be committed; live keys remain environment-only.
