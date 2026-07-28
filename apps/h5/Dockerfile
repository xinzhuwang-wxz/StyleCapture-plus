FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS build

ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}
ENV COREPACK_NPM_REGISTRY=${NPM_CONFIG_REGISTRY}

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/h5/package.json apps/h5/package.json
RUN pnpm install --frozen-lockfile --filter @stylecapture/h5...

COPY apps/h5 apps/h5
COPY skills/scene-outfit-matching skills/scene-outfit-matching
RUN pnpm --filter @stylecapture/h5 build \
    && mkdir -p apps/h5/dist/docs-assets \
    && cp apps/h5/node_modules/swagger-ui-dist/swagger-ui-bundle.js apps/h5/dist/docs-assets/ \
    && cp apps/h5/node_modules/swagger-ui-dist/swagger-ui.css apps/h5/dist/docs-assets/ \
    && cp apps/h5/node_modules/swagger-ui-dist/LICENSE apps/h5/dist/docs-assets/LICENSE \
    && mkdir -p apps/h5/dist/downloads \
    && tar -czf apps/h5/dist/downloads/scene-outfit-matching-skill.tar.gz \
        -C skills scene-outfit-matching

FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10

COPY apps/h5/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/h5/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget --quiet --spider http://127.0.0.1/healthz || exit 1
