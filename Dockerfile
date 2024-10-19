# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Install any needed packages specified in requirements.txt
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Copy the current directory contents into the container at /app
COPY ./app /app

# Set the working directory in the container
WORKDIR /app
