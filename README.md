# Memlog

A Valgrind tool that logs all floating-point writes to large memory buffers for analysis.

## CI/CD with GitHub Workflows

### Automated Build and Push (build.yml)
This workflow automatically triggers on every push to the `main` branch:

1. **Checkout Code**: Fetches the repository
2. **Generate Image Tag**: Creates a unique tag using the commit hash
3. **Update Configuration**: Automatically updates `menu.sh` with commit information
4. **Build Docker Image**: Constructs the container with all dependencies
5. **Push to ECR**: Uploads the image to AWS Elastic Container Registry with both versioned and `latest` tags

### Manual Deployment (deploy.yml)
This workflow allows manual deployment to EC2 instances:

1. **Workflow Dispatch**: Manually triggered with customizable parameters:
   - `tag`: Specify which image version to deploy (default: `latest`)
   - `baremetal_host`: Optional IP address override for deployment target
2. **Connectivity Check**: Verifies the target host is reachable
3. **Deploy**: Copies deployment script and executes it on the remote host

## Local Setup

### Prerequisites

#### For Linux:
- Docker Engine (20.10+)
- Git
- Bash shell
- SPEC CPU2017 ISO file (`cpu2017-1.1.9.iso`)

#### For WSL2 (Windows Subsystem for Linux):
- WSL2 with Ubuntu 20.04+ or similar distribution
- Docker Desktop for Windows with WSL2 backend enabled
- Git configured in WSL2
- SPEC CPU2017 ISO file accessible from WSL2

### Installation Using install.sh

The `install.sh` script automates the local build process:

```bash
# 1. Clone the repository
git clone https://github.com/enzobonansea/memlog.git
cd memlog

# 2. Place the SPEC2017 ISO in the root directory
cp /path/to/cpu2017-1.1.9.iso .

# 3. Make the installation script executable
chmod +x install.sh

# 4. Run the installation script
./install.sh
```

#### What install.sh does:

1. **Retrieves commit information** from main repository
2. **Updates menu.sh** with actual commit hash (replacing placeholder)
3. **Builds Docker image** with tag `memlog:latest`
4. **Saves image** to `~/memlog.tar` for portability
5. **Loads image** back into Docker for immediate use
6. **Restores original menu.sh** (removes temporary commit info)

### WSL2-Specific Setup

```bash
# Ensure Docker Desktop is running and WSL2 integration is enabled
docker --version

# If using Windows paths, convert them for WSL2
# Example: C:\Users\YourName\cpu2017-1.1.9.iso becomes /mnt/c/Users/YourName/cpu2017-1.1.9.iso
cp /mnt/c/path/to/cpu2017-1.1.9.iso .

# Run the installation
./install.sh
```

### Running the Container

After successful installation:

```bash
# Run the container interactively
docker run -it --rm memlog:latest

# Or with volume mounting for persistent data
docker run -it --rm -v $(pwd)/output:/workspace/output memlog:latest

# For WSL2, ensure proper path conversion
docker run -it --rm -v /mnt/c/your/windows/path:/workspace/output memlog:latest
```

## Manual Setup (Alternative)

If you prefer manual setup without the install.sh script:

```bash
# 1. Download SPEC2017 ISO
# Place cpu2017-1.1.9.iso in the root folder

# 2. Build container manually
docker build -t valgrind-memlog .

# 3. Run container
docker run -it valgrind-memlog
```

## About Memlog Tool

The memlog tool is an independent Valgrind tool that:
- Tracks memory allocations above a configurable threshold (default: 4096 bytes)
- Logs all store operations to tracked memory blocks
- Outputs the memory address, stored value (in hex), and offset within the block
- Classifies buffers as `float`, `double`, or `object` based on alignment patterns

See `valgrind/memlog/README.md` for detailed usage instructions.

## Troubleshooting

### Common Issues on WSL2:
- **Docker not found**: Ensure Docker Desktop is running and WSL2 integration is enabled in Docker Desktop settings
- **Permission denied**: Run `chmod +x install.sh` to make the script executable
- **Path issues**: Use WSL2 paths (`/mnt/c/...`) instead of Windows paths (`C:\...`)

### Common Issues on Linux:
- **Docker permission denied**: Add your user to the docker group: `sudo usermod -aG docker $USER` and re-login
- **ISO file not found**: Verify the SPEC2017 ISO is named exactly `cpu2017-1.1.9.iso`
