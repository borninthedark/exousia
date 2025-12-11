#!/bin/bash
# RKE2 VM Manager
# ===============
#
# Manage RKE2 bootc VMs with libvirt

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
VM_NAME="${RKE2_VM_NAME:-rke2-node-1}"
DISK_PATH="${RKE2_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"
DISK_SIZE="${RKE2_DISK_SIZE:-50G}"
KUBECONFIG_DIR="${RKE2_KUBECONFIG_DIR:-/var/lib/libvirt/rke2/kubeconfig}"
STORAGE_DIR="${RKE2_STORAGE_DIR:-/var/lib/libvirt/rke2/storage}"
IMAGE_REGISTRY="${RKE2_IMAGE_REGISTRY:-localhost:5000/exousia-rke2:latest}"

usage() {
    cat << EOF
Usage: $(basename "$0") COMMAND [OPTIONS]

Manage RKE2 bootc VMs

COMMANDS:
    build       Build bootc disk image
    create      Create VM from bootc image
    start       Start VM
    stop        Stop VM
    restart     Restart VM
    console     Connect to VM console
    ssh         SSH into VM
    status      Show VM status
    kubeconfig  Get kubeconfig from VM
    destroy     Destroy VM (keeps disk)
    purge       Destroy VM and remove disk
    info        Show VM information

ENVIRONMENT:
    RKE2_VM_NAME            VM name (default: rke2-node-1)
    RKE2_DISK_PATH          Disk path (default: /var/lib/libvirt/images/rke2-node-1.qcow2)
    RKE2_DISK_SIZE          Disk size (default: 50G)
    RKE2_KUBECONFIG_DIR     Kubeconfig directory (default: /var/lib/libvirt/rke2/kubeconfig)
    RKE2_STORAGE_DIR        Storage directory (default: /var/lib/libvirt/rke2/storage)
    RKE2_IMAGE_REGISTRY     Container image (default: localhost:5000/exousia-rke2:latest)

EXAMPLES:
    # Build bootc disk image
    $(basename "$0") build

    # Create and start VM
    $(basename "$0") create
    $(basename "$0") start

    # Get kubeconfig
    $(basename "$0") kubeconfig

    # Check status
    $(basename "$0") status
EOF
}

# Build bootc disk image
build_image() {
    echo -e "${BLUE}Building bootc disk image...${NC}"

    # Create output directory
    mkdir -p "$(dirname "$DISK_PATH")"

    # Build disk image using bootc-image-builder
    echo "Building from: $IMAGE_REGISTRY"
    echo "Output: $DISK_PATH"

    sudo podman run --rm -it --privileged \
        --pull=newer \
        --security-opt label=type:unconfined_t \
        -v /var/lib/containers/storage:/var/lib/containers/storage \
        -v "$(dirname "$DISK_PATH"):/output" \
        -v ./k8s/rke2/cloud-init.yaml:/config/cloud-init.yaml:ro \
        quay.io/centos-bootc/bootc-image-builder:latest \
        --type qcow2 \
        --rootfs "$DISK_SIZE" \
        "$IMAGE_REGISTRY"

    # Move image to correct location
    if [ -f "$(dirname "$DISK_PATH")/qcow2/disk.qcow2" ]; then
        sudo mv "$(dirname "$DISK_PATH")/qcow2/disk.qcow2" "$DISK_PATH"
        sudo rm -rf "$(dirname "$DISK_PATH")/qcow2"
        sudo chown "$USER:$USER" "$DISK_PATH"
        echo -e "${GREEN}✓${NC} Disk image built: $DISK_PATH"
    else
        echo -e "${RED}✗${NC} Failed to build disk image"
        exit 1
    fi
}

# Create VM
create_vm() {
    if virsh list --all | grep -q "$VM_NAME"; then
        echo -e "${YELLOW}VM $VM_NAME already exists${NC}"
        return 0
    fi

    echo -e "${BLUE}Creating VM $VM_NAME...${NC}"

    # Create shared directories
    sudo mkdir -p "$KUBECONFIG_DIR"
    sudo mkdir -p "$STORAGE_DIR"
    sudo chmod 755 "$KUBECONFIG_DIR" "$STORAGE_DIR"

    # Check if disk exists
    if [ ! -f "$DISK_PATH" ]; then
        echo -e "${RED}✗${NC} Disk image not found: $DISK_PATH"
        echo "Build it first with: $0 build"
        exit 1
    fi

    # Define VM from XML template
    # Note: This uses the libvirt-domain.xml template
    # You may need to customize it first
    if [ -f "k8s/rke2/libvirt-domain.xml" ]; then
        # Update XML with actual paths
        sed "s|/var/lib/libvirt/images/rke2-node-1.qcow2|$DISK_PATH|g; \
             s|/var/lib/libvirt/rke2/kubeconfig|$KUBECONFIG_DIR|g; \
             s|/var/lib/libvirt/rke2/storage|$STORAGE_DIR|g; \
             s|<name>rke2-node-1</name>|<name>$VM_NAME</name>|g" \
             k8s/rke2/libvirt-domain.xml > /tmp/rke2-domain.xml

        sudo virsh define /tmp/rke2-domain.xml
        rm /tmp/rke2-domain.xml
        echo -e "${GREEN}✓${NC} VM defined: $VM_NAME"
    else
        echo -e "${RED}✗${NC} libvirt-domain.xml not found"
        exit 1
    fi
}

# Start VM
start_vm() {
    if ! virsh list --all | grep -q "$VM_NAME"; then
        echo -e "${RED}✗${NC} VM $VM_NAME does not exist"
        echo "Create it first with: $0 create"
        exit 1
    fi

    if virsh list | grep -q "$VM_NAME"; then
        echo -e "${YELLOW}VM $VM_NAME is already running${NC}"
        return 0
    fi

    echo -e "${BLUE}Starting VM $VM_NAME...${NC}"
    sudo virsh start "$VM_NAME"
    echo -e "${GREEN}✓${NC} VM started"

    echo "Waiting for VM to boot..."
    sleep 10

    get_vm_ip
}

# Stop VM
stop_vm() {
    if ! virsh list | grep -q "$VM_NAME"; then
        echo -e "${YELLOW}VM $VM_NAME is not running${NC}"
        return 0
    fi

    echo -e "${BLUE}Stopping VM $VM_NAME...${NC}"
    sudo virsh shutdown "$VM_NAME"
    echo -e "${GREEN}✓${NC} VM shutdown initiated"
}

# Restart VM
restart_vm() {
    stop_vm
    sleep 5
    start_vm
}

# Get VM IP
get_vm_ip() {
    echo -e "${BLUE}Getting VM IP address...${NC}"
    sleep 5  # Wait for DHCP

    VM_IP=$(sudo virsh domifaddr "$VM_NAME" | grep -oP '(?<=ipv4\s{1,})[\d.]+' | head -1)

    if [ -n "$VM_IP" ]; then
        echo -e "${GREEN}✓${NC} VM IP: $VM_IP"
        echo "$VM_IP" > /tmp/rke2-vm-ip
    else
        echo -e "${YELLOW}⚠${NC} Could not determine VM IP"
        echo "Check with: sudo virsh domifaddr $VM_NAME"
    fi
}

# Console access
console_vm() {
    echo "Connecting to VM console (Ctrl+] to exit)..."
    sudo virsh console "$VM_NAME"
}

# SSH access
ssh_vm() {
    if [ ! -f /tmp/rke2-vm-ip ]; then
        get_vm_ip
    fi

    VM_IP=$(cat /tmp/rke2-vm-ip 2>/dev/null)
    if [ -z "$VM_IP" ]; then
        echo -e "${RED}✗${NC} VM IP not found"
        exit 1
    fi

    ssh "core@$VM_IP"
}

# Show status
show_status() {
    echo -e "${BLUE}VM Status:${NC}"
    sudo virsh list --all | grep "$VM_NAME" || echo "VM not found"

    if virsh list | grep -q "$VM_NAME"; then
        echo ""
        echo -e "${BLUE}VM Info:${NC}"
        sudo virsh dominfo "$VM_NAME"

        echo ""
        echo -e "${BLUE}Network:${NC}"
        sudo virsh domifaddr "$VM_NAME"
    fi
}

# Get kubeconfig
get_kubeconfig() {
    echo -e "${BLUE}Checking for kubeconfig...${NC}"

    KUBECONFIG_FILE="$KUBECONFIG_DIR/rke2.yaml"

    if [ -f "$KUBECONFIG_FILE" ]; then
        echo -e "${GREEN}✓${NC} Kubeconfig found: $KUBECONFIG_FILE"

        # Get VM IP for updating server address
        if [ ! -f /tmp/rke2-vm-ip ]; then
            get_vm_ip
        fi
        VM_IP=$(cat /tmp/rke2-vm-ip 2>/dev/null)

        # Copy and update kubeconfig
        mkdir -p ~/.kube
        cp "$KUBECONFIG_FILE" ~/.kube/rke2-config

        if [ -n "$VM_IP" ]; then
            sed -i "s|https://127.0.0.1:6443|https://${VM_IP}:6443|g" ~/.kube/rke2-config
            echo -e "${GREEN}✓${NC} Kubeconfig copied to ~/.kube/rke2-config"
            echo ""
            echo "Use it with:"
            echo "  export KUBECONFIG=~/.kube/rke2-config"
            echo "  kubectl cluster-info"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Kubeconfig not found yet"
        echo "Wait for RKE2 to start, then try again"
    fi
}

# Destroy VM
destroy_vm() {
    echo -e "${BLUE}Destroying VM $VM_NAME...${NC}"

    if virsh list | grep -q "$VM_NAME"; then
        sudo virsh destroy "$VM_NAME"
    fi

    sudo virsh undefine "$VM_NAME" || true
    echo -e "${GREEN}✓${NC} VM destroyed (disk preserved)"
}

# Purge VM
purge_vm() {
    destroy_vm

    echo -e "${BLUE}Removing disk...${NC}"
    sudo rm -f "$DISK_PATH"

    echo -e "${BLUE}Removing shared directories...${NC}"
    sudo rm -rf "$KUBECONFIG_DIR" "$STORAGE_DIR"

    echo -e "${GREEN}✓${NC} VM purged"
}

# Show info
show_info() {
    cat << EOF
${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}
${BLUE}║              RKE2 VM Configuration                        ║${NC}
${BLUE}╠═══════════════════════════════════════════════════════════╣${NC}

${YELLOW}VM Name:${NC}        $VM_NAME
${YELLOW}Disk Path:${NC}      $DISK_PATH
${YELLOW}Disk Size:${NC}      $DISK_SIZE
${YELLOW}Kubeconfig:${NC}     $KUBECONFIG_DIR
${YELLOW}Storage:${NC}        $STORAGE_DIR
${YELLOW}Image:${NC}          $IMAGE_REGISTRY

${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}
EOF
}

# Main command handler
case "${1:-}" in
    build)
        build_image
        ;;
    create)
        create_vm
        ;;
    start)
        start_vm
        ;;
    stop)
        stop_vm
        ;;
    restart)
        restart_vm
        ;;
    console)
        console_vm
        ;;
    ssh)
        ssh_vm
        ;;
    status)
        show_status
        ;;
    kubeconfig)
        get_kubeconfig
        ;;
    destroy)
        destroy_vm
        ;;
    purge)
        purge_vm
        ;;
    info)
        show_info
        ;;
    -h|--help|help)
        usage
        exit 0
        ;;
    "")
        echo "Missing command"
        usage
        exit 1
        ;;
    *)
        echo "Unknown command: $1"
        usage
        exit 1
        ;;
esac
