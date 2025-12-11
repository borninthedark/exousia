#!/bin/bash
# RKE2 Kubeconfig Helper Script
# ==============================
#
# Display kubeconfig for kubectl access or export it

set -euo pipefail

KUBECONFIG_PATH="/etc/rancher/rke2/rke2.yaml"
HOST_EXPORT_PATH="/mnt/host/kubeconfig/rke2.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Display or export RKE2 kubeconfig for kubectl access

OPTIONS:
    -d, --display       Display kubeconfig content (default)
    -e, --export        Export kubeconfig to host mount
    -p, --path          Show kubeconfig file path
    -h, --help          Show this help message

EXAMPLES:
    # Display kubeconfig
    $(basename "$0") --display

    # Export to host
    $(basename "$0") --export

    # Get file path for KUBECONFIG env var
    export KUBECONFIG=\$($(basename "$0") --path)

USAGE FROM HOST:
    # Copy kubeconfig from VM to host (if exported)
    cp /path/to/vm/mount/rke2.yaml ~/.kube/config

    # Update server address to VM IP
    sed -i 's|https://127.0.0.1:6443|https://192.168.122.100:6443|' ~/.kube/config

    # Test connection
    kubectl cluster-info
EOF
}

display_kubeconfig() {
    if [ ! -f "$KUBECONFIG_PATH" ]; then
        echo -e "${RED}✗${NC} Kubeconfig not found at $KUBECONFIG_PATH"
        echo "  RKE2 may not be initialized yet"
        exit 1
    fi

    echo -e "${BLUE}Kubeconfig content:${NC}"
    cat "$KUBECONFIG_PATH"
}

export_kubeconfig() {
    if [ ! -f "$KUBECONFIG_PATH" ]; then
        echo -e "${RED}✗${NC} Kubeconfig not found at $KUBECONFIG_PATH"
        exit 1
    fi

    if [ ! -d "$(dirname "$HOST_EXPORT_PATH")" ]; then
        echo -e "${YELLOW}⚠${NC} Host mount point not found: $(dirname "$HOST_EXPORT_PATH")"
        echo "  Ensure /mnt/host/kubeconfig is mounted from host"
        exit 1
    fi

    cp "$KUBECONFIG_PATH" "$HOST_EXPORT_PATH"
    chmod 644 "$HOST_EXPORT_PATH"
    echo -e "${GREEN}✓${NC} Kubeconfig exported to $HOST_EXPORT_PATH"
    echo ""
    echo "On the host, copy and update the server address:"
    echo "  cp /path/to/mount/rke2.yaml ~/.kube/config"
    echo "  sed -i 's|https://127.0.0.1:6443|https://VM_IP:6443|' ~/.kube/config"
}

show_path() {
    echo "$KUBECONFIG_PATH"
}

# Parse arguments
case "${1:-}" in
    -d|--display)
        display_kubeconfig
        ;;
    -e|--export)
        export_kubeconfig
        ;;
    -p|--path)
        show_path
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    "")
        display_kubeconfig
        ;;
    *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
esac
