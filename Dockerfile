# Use the official Ubuntu 20.04 image as the base image
FROM ubuntu:20.04

# Set the maintainer label (optional)
LABEL maintainer="Francesco <francesco.decampo@andovar.com>"

# Set the working directory to /app
WORKDIR /app

# Prevent time zone configuration from blocking the build process
ENV DEBIAN_FRONTEND=noninteractive

# Update the package list after adding the repository
RUN apt-get update

# Install Python 3.10
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    build-essential

# Copy the contents of the local directory into the container at /app
COPY . /app

# Install Python dependencies from requirements.txt using pip3
RUN pip3 install -r requirements.txt

# Expose the port that your Streamlit app runs on (e.g., 8501)
EXPOSE 8501

# Command to run the Streamlit app
CMD ["streamlit", "run", "svo-batch-generator.py"]