#!/bin/bash
# Configuration Installation Audit Script
# Verifies all custom configurations are properly configured for installation

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Exousia Configuration Installation Audit"
echo "=================================================="
echo ""

total_files=0
found_files=0
missing_files=0

check_file() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"

    total_files=$((total_files + 1))

    if [ -e "$src" ]; then
        echo -e "${GREEN}✓${NC} $src → $dst (mode: $mode)"
        found_files=$((found_files + 1))
    else
        echo -e "${RED}✗${NC} $src → $dst (mode: $mode) - SOURCE MISSING"
        missing_files=$((missing_files + 1))
    fi
}

check_directory() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"

    if [ -d "$src" ]; then
        local count=$(find "$src" -type f | wc -l)
        echo -e "${GREEN}✓${NC} $src → $dst (mode: $mode) - $count files"
        found_files=$((found_files + count))
        total_files=$((total_files + count))

        # List files in directory
        find "$src" -type f | while read -r file; do
            rel_path="${file#$src/}"
            echo "  - $rel_path → $dst/$rel_path"
        done
    else
        echo -e "${RED}✗${NC} $src → $dst (mode: $mode) - DIRECTORY MISSING"
        missing_files=$((missing_files + 1))
        total_files=$((total_files + 1))
    fi
}

echo "### 1. System Users Configuration"
check_file "sysusers/bootc.conf" "/usr/lib/sysusers.d/bootc.conf" "0644"
echo ""

echo "### 2. Container Authentication"
check_file "containers-auth.conf" "/usr/lib/tmpfiles.d/containers-auth.conf" "0644"
check_file "./bootc-secrets/auth.json" "/usr/lib/container-auth.json" "0600"
echo ""

echo "### 3. Plymouth Theme (conditional: enable_plymouth)"
check_directory "custom-configs/plymouth/themes/bgrt-better-luks" "/usr/share/plymouth/themes/bgrt-better-luks" "0644"
echo ""

echo "### 4. Custom Repositories"
check_directory "custom-repos" "/etc/yum.repos.d" "0644"
echo ""

echo "### 5. Custom Configurations (PRIMARY CONFIG DIRECTORY)"
echo "Source: custom-configs/ → Destination: /etc/ (mode: 0644)"
if [ -d "custom-configs" ]; then
    echo -e "${GREEN}✓${NC} custom-configs/ directory exists"
    echo ""
    echo "#### Configuration breakdown by category:"

    echo "##### 5.1 Display Manager (greetd)"
    check_file "custom-configs/greetd/config.toml" "/etc/greetd/config.toml" "0644"
    echo ""

    echo "##### 5.2 PAM U2F Authentication"
    check_file "custom-configs/pam.d/sudo" "/etc/pam.d/sudo" "0644"
    check_file "custom-configs/pam.d/u2f-required" "/etc/pam.d/u2f-required" "0644"
    check_file "custom-configs/pam.d/u2f-sufficient" "/etc/pam.d/u2f-sufficient" "0644"
    echo ""

    echo "##### 5.3 RKE2 Kubernetes Configuration"
    check_file "custom-configs/rancher/rke2/config.yaml" "/etc/rancher/rke2/config.yaml" "0644"
    check_file "custom-configs/rancher/rke2/registries.yaml" "/etc/rancher/rke2/registries.yaml" "0644"
    check_file "custom-configs/rancher/rke2/kubeconfig-export.conf" "/etc/rancher/rke2/kubeconfig-export.conf" "0644"
    check_file "custom-configs/rancher/rke2/motd" "/etc/motd" "0644"
    echo ""

    echo "##### 5.4 Sway Window Manager Configuration"
    check_file "custom-configs/sway/config" "/etc/sway/config" "0644"
    check_directory "custom-configs/sway/config.d" "/etc/sway/config.d" "0644"
    echo ""

    echo "##### 5.5 Swaylock Configuration"
    check_file "custom-configs/swaylock/config" "/etc/swaylock/config" "0644"
    echo ""

    echo "##### 5.6 Tmpfiles.d Configuration (NEW - dnsmasq fix)"
    check_file "custom-configs/tmpfiles.d/libvirt-dnsmasq.conf" "/etc/tmpfiles.d/libvirt-dnsmasq.conf" "0644"
    echo ""
else
    echo -e "${RED}✗${NC} custom-configs/ directory missing"
    missing_files=$((missing_files + 1))
fi

echo "### 6. Custom Scripts"
check_directory "custom-scripts" "/usr/local/bin" "0755"
echo ""

echo "### 7. Sway Session Files (special mappings)"
check_file "custom-configs/sway/sway.desktop" "/usr/share/wayland-sessions/sway.desktop" "0644"
check_file "custom-configs/sway/environment" "/etc/sway/environment" "0644"
check_file "custom-configs/sway/start-sway" "/usr/bin/start-sway" "0755"
check_file "custom-scripts/layered-include" "/usr/libexec/sway/layered-include" "0755"
check_file "custom-scripts/volume-helper" "/usr/libexec/sway/volume-helper" "0755"
echo ""

echo "### 8. RKE2 Management Tool (conditional: enable_rke2)"
check_file "tools/rke2_ops.py" "/usr/local/bin/rke2_ops" "0755"
echo ""

echo "=================================================="
echo "Audit Summary"
echo "=================================================="
echo "Total files checked: $total_files"
echo -e "${GREEN}Found: $found_files${NC}"
echo -e "${RED}Missing: $missing_files${NC}"
echo ""

if [ $missing_files -eq 0 ]; then
    echo -e "${GREEN}✓ All configuration files are properly configured!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some configuration files are missing. Please review above.${NC}"
    exit 1
fi
