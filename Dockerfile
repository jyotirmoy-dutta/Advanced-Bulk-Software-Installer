# Cross-Platform Bulk Software Installer Docker Image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Go
RUN wget https://golang.org/dl/go1.21.0.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz \
    && rm go1.21.0.linux-amd64.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# Install Snap
RUN apt-get update && apt-get install -y snapd
RUN ln -s /var/lib/snapd/snap /snap

# Install Flatpak
RUN apt-get update && apt-get install -y flatpak
RUN flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY bulk_installer.py .
COPY configs/ ./configs/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Create a non-root user
RUN useradd -m -u 1000 installer
RUN chown -R installer:installer /app
USER installer

# Expose port for web interface (if implemented)
EXPOSE 8080

# Set default command
CMD ["python", "bulk_installer.py", "--help"] 