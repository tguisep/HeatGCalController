SHELL := /bin/bash

# Specify the installation path)
INSTALL_PATH ?= /opt/heatzy/pilotes/google-calendar
INSTALL_CONFIG_PATH  ?= /etc/heatzy/pilotes/google-calendar

INSTALL_CONFIG_FILE ?= ./configs/configs.yaml

# Get current script directory
mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
mkfile_dir := $(dir $(mkfile_path))

# Define the help message
.PHONY: install clean
YQ := yq

install:
	@echo "Create user heatzy and add it to the docker group..."
	# Create the user heatzy  if it doesn't exist
	sudo id -u heatzy &>/dev/null
	# If the user doesn't exist, create it
	if [ $$? -ne 0 ]; then \
		echo "User heatzy doesn't exist. Creating it..."; \
		sudo useradd -r -s /bin/false heatzy ; \
		sudo usermod -aG docker heatzy ; \
	fi

	@echo "Create the installation directory..."
	sudo mkdir -p "$(INSTALL_PATH)/app/"
	@echo "Copy the files to the installation directory..."
	# Get the directory of the running script
	@echo "SCRIPT_DIR: $(mkfile_dir)"
	# Test if SCRIPT_DIR is empty
	if [ -z "$(mkfile_dir)" ]; then \
		echo "Error: SCRIPT_DIR is empty"; \
		exit 1; \
	fi
	# Copy the app files
	sudo cp -r "$(mkfile_dir)"/app/* "$(INSTALL_PATH)/app/"
	# Copy the docker-compose file
	sudo cp "$(mkfile_dir)/docker-compose.yaml" "$(INSTALL_PATH)/docker-compose.yaml"
	# Copy the dockerfile
	sudo cp "$(mkfile_dir)/Dockerfile" "$(INSTALL_PATH)/Dockerfile"
	# Copy the requirements filee
	sudo cp "$(mkfile_dir)/requirements.txt" "$(INSTALL_PATH)/requirements.txt"


	@echo "Change the owner of the installation directory..."
	sudo chown heatzy:heatzy "$(INSTALL_PATH)" -R

	@echo "Check if docker-compose is installed..."
	@command -v docker-compose >/dev/null 2>&1 || { echo >&2 "docker-compose is not installed. Aborting."; exit 1; }

	@echo "Building the docker image..."
	sudo docker-compose -f "$(INSTALL_PATH)/docker-compose.yaml" build

	@echo "Install with systemd"

	@echo "Moving files to systemd directory..."
	sudo cp install/system.d/get_schedules.timer  /etc/systemd/system/
	sudo cp install/system.d/get_schedules.service /etc/systemd/system/
	sudo cp install/system.d/set_heaters.timer /etc/systemd/system/
	sudo cp install/system.d/set_heaters.service /etc/systemd/system/


	@echo "Setting the installation path in the systemd services files..."
	sudo sed -i "s|%%INSTALL_PATH%%|$(INSTALL_PATH)|g" /etc/systemd/system/set_heaters.service
	sudo sed -i "s|%%INSTALL_PATH%%|$(INSTALL_PATH)|g" /etc/systemd/system/get_schedules.service

	@echo "Setting the run intervals in systemd timers files..."
	sudo sed -i "s|%%SET_HEATERS_RUN_INTERVAL%%|60s|g" /etc/systemd/system/set_heaters.timer
	sudo sed -i "s|%%GET_SCHEDULES_RUN_INTERVAL%%|5m|g" /etc/systemd/system/get_schedules.timer


	@echo "Create the configuration directory..."
	sudo mkdir -p "$(INSTALL_CONFIG_PATH)"

	@echo "Deploy credentials..."
	sudo mkdir -p "$(INSTALL_PATH)/credentials"
	sudo cp "$(mkfile_dir)"/credentials/* "$(INSTALL_PATH)/credentials"
	if [ -L "$(INSTALL_CONFIG_PATH)/credentials" ]; then \
		echo "Symbolic $(INSTALL_CONFIG_PATH)/credentials link exists. Removing..."; \
		sudo rm "$(INSTALL_CONFIG_PATH)/credentials"; \
	fi
	sudo ln -s "$(INSTALL_PATH)/credentials" "$(INSTALL_CONFIG_PATH)/credentials"

	@echo "Deploy configurations..."
	sudo mkdir -p "$(INSTALL_PATH)/configs"
	sudo cp "$(mkfile_dir)"/configs/* "$(INSTALL_PATH)/configs"
	if [ -L "$(INSTALL_CONFIG_PATH)/configs" ]; then \
		echo "Symbolic $(INSTALL_CONFIG_PATH)/configs link exists. Removing..."; \
		sudo rm "$(INSTALL_CONFIG_PATH)/configs"; \
	fi
	sudo ln -s "$(INSTALL_PATH)/configs" "$(INSTALL_CONFIG_PATH)/configs"

	@echo "Reloading systemd..."
	sudo systemctl daemon-reload

	@echo "Enabling and starting the timers..."
	sudo systemctl enable get_schedules.timer
	sudo systemctl enable set_heaters.timer
	sudo systemctl start get_schedules.timer
	sudo systemctl start set_heaters.timer


clean:

	@echo "Stopping and disabling the timers..."
	sudo systemctl stop get_schedules.timer
	sudo systemctl stop set_heaters.timer
	sudo systemctl disable get_schedules.timer
	sudo systemctl disable set_heaters.timer

	@echo "Removing files from systemd directory..."
	sudo rm -f /etc/systemd/system/get_schedules.timer
	sudo rm -f /etc/systemd/system/set_heaters.timer
	sudo rm -f /etc/systemd/system/get_schedules.service
	sudo rm -f /etc/systemd/system/set_heaters.service


	@echo "Remove app files"
	sudo rm -f "$(INSTALL_PATH)/app"
	sudo rm -f "$(INSTALL_PATH)/docker-compose.yaml"
	sudo rm -f "$(INSTALL_PATH)/Dockerfile"
	sudo rm -f "$(INSTALL_PATH)/requirements.txt"

	@echo "Remove configurations files"
	sudo rm -f "$(INSTALL_CONFIG_PATH)/configs"
	sudo rm -f "$(INSTALL_CONFIG_PATH)/credentials"

