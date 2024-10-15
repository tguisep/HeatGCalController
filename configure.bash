#!/bin/bash


# Print a message indicating the script is configuring
echo "Check packaging..."

# YQ required
if ! command -v yq &> /dev/null; then
  echo "yq is not installed."
    echo "For Ubuntu / Debian, you can use: sudo apt-get install yq"
  exit 1
fi

USE_COMPOSE=$(shell yq '.install.use_compose' "${INSTALL_CONFIG_FILE}")
if [ -z "${USE_COMPOSE}" ]; then
  echo "USE_COMPOSE is not defined."
  exit 1
fi

USE_SYSTEMD=$(yq '.install.use_systemd' "$INSTALL_CONFIG_FILE")
if [ -z "${USE_SYSTEMD}" ]; then
  echo "USE_SYSTEMD is not defined."
  exit 1
fi

SET_HEATERS_RUN_INTERVAL=$(yq '.set_heaters.run_interval' "$INSTALL_CONFIG_FILE")
if [ -z "${SET_HEATERS_RUN_INTERVAL}" ]; then
  echo "SET_HEATERS_RUN_INTERVAL is not defined."
  exit 1
fi

GET_SCHEDULES_RUN_INTERVAL=$(yq '.get_schedules.run_interval' "$INSTALL_CONFIG_FILE")
if [ -z "${GET_SCHEDULES_RUN_INTERVAL}" ]; then
  echo "GET_SCHEDULES_RUN_INTERVAL is not defined."
  exit 1
fi

if [ "${USE_COMPOSE}" == "true" ]; then
  echo "Install with docker-compose"
  if command -v docker-compose &> /dev/null ; then
  echo "docker-compose is not installed."
  exit 1
  fi
fi