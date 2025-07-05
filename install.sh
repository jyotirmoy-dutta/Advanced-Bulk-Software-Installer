#!/bin/bash

# Cross-Platform Bulk Software Installer Setup Script
# This script sets up the bulk installer on Linux and macOS systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Function to install Python
install_python() {
    local os=$1
    
    if command -v python3 &> /dev/null; then
        print_success "Python 3 is already installed"
        return 0
    fi
    
    print_status "Installing Python 3..."
    
    case $os in
        "linux")
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y python3 python3-pip
            elif command -v yum &> /dev/null; then
                sudo yum install -y python3 python3-pip
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y python3 python3-pip
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm python python-pip
            else
                print_error "Unsupported Linux distribution"
                return 1
            fi
            ;;
        "macos")
            if command -v brew &> /dev/null; then
                brew install python3
            else
                print_error "Homebrew not found. Please install Homebrew first:"
                print_error "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                return 1
            fi
            ;;
        *)
            print_error "Unsupported operating system"
            return 1
            ;;
    esac
    
    print_success "Python 3 installed successfully"
}

# Function to install package managers
install_package_managers() {
    local os=$1
    
    print_status "Installing package managers..."
    
    case $os in
        "linux")
            # Install common package managers
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y snapd flatpak
                sudo systemctl enable --now snapd.socket
            elif command -v yum &> /dev/null; then
                sudo yum install -y snapd flatpak
                sudo systemctl enable --now snapd.socket
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y snapd flatpak
                sudo systemctl enable --now snapd.socket
            fi
            
            # Install pip if not available
            if ! command -v pip3 &> /dev/null; then
                print_status "Installing pip..."
                curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
                python3 get-pip.py --user
                rm get-pip.py
            fi
            
            # Install Node.js and npm
            if ! command -v npm &> /dev/null; then
                print_status "Installing Node.js and npm..."
                curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
                sudo apt-get install -y nodejs
            fi
            
            # Install Rust (for cargo)
            if ! command -v cargo &> /dev/null; then
                print_status "Installing Rust..."
                curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
                source ~/.cargo/env
            fi
            
            # Install Go
            if ! command -v go &> /dev/null; then
                print_status "Installing Go..."
                wget https://golang.org/dl/go1.21.0.linux-amd64.tar.gz
                sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
                echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
                source ~/.bashrc
                rm go1.21.0.linux-amd64.tar.gz
            fi
            ;;
            
        "macos")
            # Install Homebrew if not available
            if ! command -v brew &> /dev/null; then
                print_status "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
                eval "$(/opt/homebrew/bin/brew shellenv)"
            fi
            
            # Install Node.js and npm
            if ! command -v npm &> /dev/null; then
                print_status "Installing Node.js and npm..."
                brew install node
            fi
            
            # Install Rust
            if ! command -v cargo &> /dev/null; then
                print_status "Installing Rust..."
                curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
                source ~/.cargo/env
            fi
            
            # Install Go
            if ! command -v go &> /dev/null; then
                print_status "Installing Go..."
                brew install go
            fi
            ;;
    esac
    
    print_success "Package managers installed successfully"
}

# Function to install Python dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
        print_success "Python dependencies installed successfully"
    else
        print_warning "requirements.txt not found, installing basic dependencies..."
        pip3 install requests pathlib2 typing-extensions
        print_success "Basic dependencies installed"
    fi
}

# Function to make script executable
make_executable() {
    print_status "Making bulk installer executable..."
    chmod +x bulk_installer.py
    print_success "Bulk installer is now executable"
}

# Function to create sample configuration
create_sample_config() {
    if [ ! -f "apps.json" ]; then
        print_status "Creating sample configuration file..."
        cat > apps.json << 'EOF'
[
  {
    "name": "git",
    "manager": "apt",
    "tags": ["development", "version-control"],
    "priority": 10
  },
  {
    "name": "python3",
    "manager": "apt",
    "tags": ["development", "python"],
    "priority": 9
  },
  {
    "name": "nodejs",
    "manager": "apt",
    "tags": ["development", "javascript"],
    "priority": 8
  },
  {
    "name": "docker.io",
    "manager": "apt",
    "tags": ["development", "containerization"],
    "priority": 7
  },
  {
    "name": "code",
    "manager": "snap",
    "tags": ["development", "editor"],
    "priority": 6
  },
  {
    "name": "firefox",
    "manager": "apt",
    "tags": ["browser", "web"],
    "priority": 5
  },
  {
    "name": "vlc",
    "manager": "apt",
    "tags": ["media", "video"],
    "priority": 4
  },
  {
    "name": "htop",
    "manager": "apt",
    "tags": ["utility", "system"],
    "priority": 3
  }
]
EOF
        print_success "Sample configuration created: apps.json"
    else
        print_status "Configuration file already exists: apps.json"
    fi
}

# Function to run test
run_test() {
    print_status "Running test installation..."
    
    if command -v python3 &> /dev/null; then
        python3 bulk_installer.py dry-run --config apps.json
        print_success "Test completed successfully"
    else
        print_error "Python 3 not found"
        return 1
    fi
}

# Main installation function
main() {
    print_status "Starting Cross-Platform Bulk Software Installer Setup"
    
    # Detect OS
    OS=$(detect_os)
    print_status "Detected OS: $OS"
    
    if [ "$OS" = "unknown" ]; then
        print_error "Unsupported operating system"
        exit 1
    fi
    
    # Install Python
    install_python "$OS"
    
    # Install package managers
    install_package_managers "$OS"
    
    # Install Python dependencies
    install_dependencies
    
    # Make script executable
    make_executable
    
    # Create sample configuration
    create_sample_config
    
    # Run test
    run_test
    
    print_success "Setup completed successfully!"
    echo
    print_status "Usage examples:"
    echo "  python3 bulk_installer.py install                    # Install all apps"
    echo "  python3 bulk_installer.py install --tags development # Install dev tools only"
    echo "  python3 bulk_installer.py update                     # Update all apps"
    echo "  python3 bulk_installer.py dry-run                    # Test without changes"
    echo
    print_status "For more information, see README_Cross_Platform.md"
}

# Run main function
main "$@" 