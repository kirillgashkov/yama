FROM python:3.11-slim AS base

ENV UID=1000 GID=1000 HOME=/user
ENV APP="$HOME/app"
RUN groupadd --gid "$GID" user \
 && useradd --uid "$UID" --gid "$GID" --home-dir "$HOME" --shell /bin/bash user \
 && mkdir "$HOME" \
 && chown "$UID:$GID" "$HOME" \
 && mkdir "$APP" \
 && chown "$UID:$GID" "$APP"

WORKDIR "$APP"


FROM base AS builder

ENV MIGRATE_RELEASE_TAG=v4.17.1
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/* \
 && curl -sSL "https://github.com/golang-migrate/migrate/releases/download/${MIGRATE_RELEASE_TAG}/migrate.linux-amd64.tar.gz" | tar -xz -C /usr/local/bin migrate \
 && chown root:root /usr/local/bin/migrate

USER "$UID:$GID"

COPY requirements.txt ./
RUN python -m venv .venv \
 && . .venv/bin/activate \
 && pip install --no-deps --require-hashes --constraint requirements.txt --requirement requirements.txt


FROM base AS runner

RUN mkdir /var/lib/yama \
 && chown "$UID:$GID" /var/lib/yama \
 && mkdir /var/lib/yama/file-system \
 && chown "$UID:$GID" /var/lib/yama/file-system
VOLUME /var/lib/yama/file-system

USER "$UID:$GID"

COPY --from=builder /usr/local/bin/migrate /usr/local/bin/migrate
COPY . ./
COPY --from=builder "$APP/.venv" .venv

ENV PATH="$APP/.venv/bin:$PATH" PYTHONPATH="$APP:$PYTHONPATH"

ENTRYPOINT ["python", "-m", "yama"]
