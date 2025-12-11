#!/bin/bash
# RKE2 Status Check Script
# =========================
#
# Quick status overview of RKE2 cluster

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              RKE2 Cluster Status                          ║${NC}"
echo -e "${BLUE}╠═══════════════════════════════════════════════════════════╣${NC}"

# Check RKE2 service status
echo -e "\n${YELLOW}RKE2 Service Status:${NC}"
if systemctl is-active --quiet rke2-server.service; then
    echo -e "${GREEN}✓${NC} rke2-server.service is running"
    systemctl status rke2-server.service --no-pager -l | head -n 5
else
    echo -e "${RED}✗${NC} rke2-server.service is not running"
    echo "  Start with: sudo systemctl start rke2-server.service"
fi

# Check if kubectl is available
if [ -f /var/lib/rancher/rke2/bin/kubectl ]; then
    export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
    export PATH=$PATH:/var/lib/rancher/rke2/bin

    echo -e "\n${YELLOW}Cluster Information:${NC}"
    kubectl cluster-info 2>/dev/null || echo -e "${RED}✗${NC} Unable to connect to cluster"

    echo -e "\n${YELLOW}Node Status:${NC}"
    kubectl get nodes -o wide 2>/dev/null || echo -e "${RED}✗${NC} Unable to get node status"

    echo -e "\n${YELLOW}System Pods:${NC}"
    kubectl get pods -n kube-system 2>/dev/null || echo -e "${RED}✗${NC} Unable to get pod status"

    echo -e "\n${YELLOW}RKE2 Version:${NC}"
    /var/lib/rancher/rke2/bin/kubectl version --short 2>/dev/null | head -n 2 || echo -e "${RED}✗${NC} Unable to get version"
else
    echo -e "\n${RED}✗${NC} kubectl not found. RKE2 may not be installed properly."
fi

# Check kubeconfig export
echo -e "\n${YELLOW}Kubeconfig Export:${NC}"
if [ -f /mnt/host/kubeconfig/rke2.yaml ]; then
    echo -e "${GREEN}✓${NC} Kubeconfig exported to host at /mnt/host/kubeconfig/rke2.yaml"
else
    echo -e "${YELLOW}⚠${NC} Kubeconfig not found at host mount point"
    echo "  Ensure /mnt/host/kubeconfig is mounted from host"
fi

# Check registry configuration
echo -e "\n${YELLOW}Registry Configuration:${NC}"
if [ -f /etc/rancher/rke2/registries.yaml ]; then
    echo -e "${GREEN}✓${NC} Registry mirrors configured"
    grep -A 2 "endpoint:" /etc/rancher/rke2/registries.yaml | grep -v "^--$" || true
else
    echo -e "${RED}✗${NC} Registry configuration not found"
fi

echo -e "\n${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
