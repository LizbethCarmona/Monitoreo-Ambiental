#!/bin/sh
set -eu

if [ "${MYSQL_DATABASE}" != "monitoreo_ambiental" ]; then
  echo "This deployment initializes only the monitoreo_ambiental schema." >&2
  exit 1
fi

mysql \
  --protocol=socket \
  --user=root \
  --password="${MYSQL_ROOT_PASSWORD}" \
  --database="${MYSQL_DATABASE}" <<SQL
CREATE USER IF NOT EXISTS 'monitoreo_app'@'%' IDENTIFIED BY '${APP_DB_PASSWORD}';
GRANT SELECT, INSERT ON monitoreo_ambiental.* TO 'monitoreo_app'@'%';
SQL
