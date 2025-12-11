#!/bin/bash
# RKE2 Host Registry Setup Script
# ================================
#
# Sets up a local container registry on the host for RKE2 VMs
# The registry runs on the libvirt bridge (virbr0) so VMs can access it

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REGISTRY_NAME="rke2-registry"
REGISTRY_PORT="5000"
REGISTRY_DATA_DIR="${REGISTRY_DATA_DIR:-$HOME/.local/share/containers/rke2-registry}"
BRIDGE_INTERFACE="${BRIDGE_INTERFACE:-virbr0}"

usage() {
    cat << EOF
Usage: $(basename "$0") [COMMAND]

Manage local container registry for RKE2 VMs

COMMANDS:
    start       Start the registry container
    stop        Stop the registry container
    status      Show registry status
    logs        Show registry logs
    restart     Restart the registry
    clean       Stop and remove registry (keeps data)
    purge       Stop, remove registry and delete data
    info        Show registry connection information

ENVIRONMENT:
    REGISTRY_DATA_DIR   Data directory for registry (default: ~/.local/share/containers/rke2-registry)
    BRIDGE_INTERFACE    Network bridge interface (default: virbr0)

EXAMPLES:
    # Start registry
    $(basename "$0") start

    # Check status
    $(basename "$0") status

    # View logs
    $(basename "$0") logs

    # Get connection info
    $(basename "$0") info
EOF
}

# Get bridge IP address
get_bridge_ip() {
    ip -4 addr show "$BRIDGE_INTERFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1
}

# Check if registry is running
is_running() {
    podman ps --filter "name=$REGISTRY_NAME" --format "{{.Names}}" | grep -q "$REGISTRY_NAME"
}

# Start registry
start_registry() {
    if is_running; then
        echo -e "${YELLOW}Registry is already running${NC}"
        return 0
    fi

    echo -e "${BLUE}Starting RKE2 registry...${NC}"

    # Create data directory
    mkdir -p "$REGISTRY_DATA_DIR"

    # Get bridge IP
    BRIDGE_IP=$(get_bridge_ip)
    if [ -z "$BRIDGE_IP" ]; then
        echo -e "${RED}Error: Could not determine bridge IP for $BRIDGE_INTERFACE${NC}"
        echo "Make sure libvirt default network is running:"
        echo "  sudo virsh net-start default"
        exit 1
    fi

    # Start registry container
    podman run -d \
        --name "$REGISTRY_NAME" \
        --restart=always \
        -p "${BRIDGE_IP}:${REGISTRY_PORT}:5000" \
        -v "${REGISTRY_DATA_DIR}:/var/lib/registry:Z" \
        -e REGISTRY_STORAGE_DELETE_ENABLED=true \
        docker.io/library/registry:2

    echo -e "${GREEN}✓${NC} Registry started successfully"
    echo ""
    show_info
}

# Stop registry
stop_registry() {
    if ! is_running; then
        echo -e "${YELLOW}Registry is not running${NC}"
        return 0
    fi

    echo -e "${BLUE}Stopping registry...${NC}"
    podman stop "$REGISTRY_NAME"
    echo -e "${GREEN}✓${NC} Registry stopped"
}

# Show status
show_status() {
    if is_running; then
        echo -e "${GREEN}✓${NC} Registry is running"
        podman ps --filter "name=$REGISTRY_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo -e "${RED}✗${NC} Registry is not running"
        if podman ps -a --filter "name=$REGISTRY_NAME" --format "{{.Names}}" | grep -q "$REGISTRY_NAME"; then
            echo "Container exists but is stopped. Start with: $0 start"
        fi
    fi
}

# Show logs
show_logs() {
    if ! is_running; then
        echo -e "${RED}✗${NC} Registry is not running"
        exit 1
    fi

    podman logs -f "$REGISTRY_NAME"
}

# Restart registry
restart_registry() {
    echo -e "${BLUE}Restarting registry...${NC}"
    stop_registry
    sleep 2
    start_registry
}

# Clean registry (remove container, keep data)
clean_registry() {
    stop_registry
    echo -e "${BLUE}Removing registry container...${NC}"
    podman rm "$REGISTRY_NAME" 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Registry container removed (data preserved)"
}

# Purge registry (remove container and data)
purge_registry() {
    clean_registry
    echo -e "${BLUE}Removing registry data...${NC}"
    rm -rf "$REGISTRY_DATA_DIR"
    echo -e "${GREEN}✓${NC} Registry data removed"
}

# Show connection information
show_info() {
    BRIDGE_IP=$(get_bridge_ip)
    if [ -z "$BRIDGE_IP" ]; then
        echo -e "${RED}Error: Could not determine bridge IP${NC}"
        return 1
    fi

    cat << EOF
${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}
${BLUE}║          RKE2 Registry Connection Information            ║${NC}
${BLUE}╠═══════════════════════════════════════════════════════════╣${NC}

${YELLOW}Registry URL (from VMs):${NC}
  http://${BRIDGE_IP}:${REGISTRY_PORT}

${YELLOW}Registry URL (from host):${NC}
  http://localhost:${REGISTRY_PORT}
  http://${BRIDGE_IP}:${REGISTRY_PORT}

${YELLOW}Data directory:${NC}
  ${REGISTRY_DATA_DIR}

${YELLOW}Push images to registry:${NC}
  # Tag image
  podman tag myimage:latest ${BRIDGE_IP}:${REGISTRY_PORT}/myimage:latest

  # Push to registry
  podman push ${BRIDGE_IP}:${REGISTRY_PORT}/myimage:latest

${YELLOW}Pull from registry (in VM):${NC}
  # Registry is configured in /etc/rancher/rke2/registries.yaml
  # Images will be pulled from ${BRIDGE_IP}:${REGISTRY_PORT} automatically

${YELLOW}Test registry:${NC}
  curl http://${BRIDGE_IP}:${REGISTRY_PORT}/v2/_catalog

${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}
EOF
}

# Main command handler
case "${1:-}" in
    start)
        start_registry
        ;;
    stop)
        stop_registry
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    restart)
        restart_registry
        ;;
    clean)
        clean_registry
        ;;
    purge)
        purge_registry
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
