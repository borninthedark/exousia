#!/usr/bin/env python3
"""
RKE2 Operations Manager
=======================

Manage RKE2 bootc infrastructure: registry, VMs, and kubeconfig.

Usage:
    rke2_ops.py registry {start,stop,status,info}
    rke2_ops.py vm {build,create,start,stop,restart,status,destroy,purge}
    rke2_ops.py kubeconfig
    rke2_ops.py quickstart
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color

# Configuration from environment or defaults
REGISTRY_NAME = "rke2-registry"
REGISTRY_PORT = "5000"
REGISTRY_DATA_DIR = os.getenv(
    "REGISTRY_DATA_DIR", f"{Path.home()}/.local/share/containers/rke2-registry"
)
BRIDGE_INTERFACE = os.getenv("BRIDGE_INTERFACE", "virbr0")

VM_NAME = os.getenv("RKE2_VM_NAME", "rke2-node-1")
DISK_PATH = os.getenv("RKE2_DISK_PATH", f"/var/lib/libvirt/images/{VM_NAME}.qcow2")
DISK_SIZE = os.getenv("RKE2_DISK_SIZE", "50G")
KUBECONFIG_DIR = os.getenv("RKE2_KUBECONFIG_DIR", "/var/lib/libvirt/rke2/kubeconfig")
STORAGE_DIR = os.getenv("RKE2_STORAGE_DIR", "/var/lib/libvirt/rke2/storage")
IMAGE_REGISTRY = os.getenv("RKE2_IMAGE_REGISTRY", "localhost:5000/exousia-rke2:latest")


def run_cmd(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command with optional output capture."""
    kwargs = {"check": check}
    if capture:
        kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True})
    return subprocess.run(cmd, **kwargs)


def get_bridge_ip() -> Optional[str]:
    """Get the IP address of the libvirt bridge."""
    try:
        result = run_cmd(
            ["ip", "-4", "addr", "show", BRIDGE_INTERFACE],
            capture=True,
            check=False
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "inet " in line:
                    return line.strip().split()[1].split("/")[0]
    except Exception:
        pass
    return None


def is_registry_running() -> bool:
    """Check if the registry container is running."""
    result = run_cmd(
        ["podman", "ps", "--filter", f"name={REGISTRY_NAME}", "--format", "{{.Names}}"],
        capture=True,
        check=False
    )
    return REGISTRY_NAME in result.stdout


def is_vm_running() -> bool:
    """Check if the VM is running."""
    result = run_cmd(
        ["virsh", "list", "--name"],
        capture=True,
        check=False
    )
    return VM_NAME in result.stdout


def is_vm_defined() -> bool:
    """Check if the VM is defined."""
    result = run_cmd(
        ["virsh", "list", "--all", "--name"],
        capture=True,
        check=False
    )
    return VM_NAME in result.stdout


# ============================================================================
# Registry Operations
# ============================================================================


def registry_start():
    """Start the local container registry."""
    if is_registry_running():
        print(f"{YELLOW}Registry is already running{NC}")
        return 0

    print(f"{BLUE}Starting RKE2 registry...{NC}")

    # Create data directory
    Path(REGISTRY_DATA_DIR).mkdir(parents=True, exist_ok=True)

    # Get bridge IP
    bridge_ip = get_bridge_ip()
    if not bridge_ip:
        print(f"{RED}Error: Could not determine bridge IP for {BRIDGE_INTERFACE}{NC}")
        print("Make sure libvirt default network is running:")
        print("  sudo virsh net-start default")
        return 1

    # Start registry
    run_cmd([
        "podman", "run", "-d",
        "--name", REGISTRY_NAME,
        "--restart=always",
        "-p", f"{bridge_ip}:{REGISTRY_PORT}:5000",
        "-v", f"{REGISTRY_DATA_DIR}:/var/lib/registry:Z",
        "-e", "REGISTRY_STORAGE_DELETE_ENABLED=true",
        "docker.io/library/registry:2"
    ])

    print(f"{GREEN}✓{NC} Registry started successfully")
    print()
    registry_info()
    return 0


def registry_stop():
    """Stop the local container registry."""
    if not is_registry_running():
        print(f"{YELLOW}Registry is not running{NC}")
        return 0

    print(f"{BLUE}Stopping registry...{NC}")
    run_cmd(["podman", "stop", REGISTRY_NAME])
    print(f"{GREEN}✓{NC} Registry stopped")
    return 0


def registry_status():
    """Show registry status."""
    if is_registry_running():
        print(f"{GREEN}✓{NC} Registry is running")
        run_cmd([
            "podman", "ps",
            "--filter", f"name={REGISTRY_NAME}",
            "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ])
    else:
        print(f"{RED}✗{NC} Registry is not running")
        result = run_cmd(
            ["podman", "ps", "-a", "--filter", f"name={REGISTRY_NAME}", "--format", "{{.Names}}"],
            capture=True,
            check=False
        )
        if REGISTRY_NAME in result.stdout:
            print(f"Container exists but is stopped. Start with: rke2_ops.py registry start")
    return 0


def registry_info():
    """Show registry connection information."""
    bridge_ip = get_bridge_ip()
    if not bridge_ip:
        print(f"{RED}Error: Could not determine bridge IP{NC}")
        return 1

    print(f"{BLUE}╔═══════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║          RKE2 Registry Connection Information            ║{NC}")
    print(f"{BLUE}╠═══════════════════════════════════════════════════════════╣{NC}")
    print()
    print(f"{YELLOW}Registry URL (from VMs):{NC}")
    print(f"  http://{bridge_ip}:{REGISTRY_PORT}")
    print()
    print(f"{YELLOW}Registry URL (from host):{NC}")
    print(f"  http://localhost:{REGISTRY_PORT}")
    print(f"  http://{bridge_ip}:{REGISTRY_PORT}")
    print()
    print(f"{YELLOW}Data directory:{NC}")
    print(f"  {REGISTRY_DATA_DIR}")
    print()
    print(f"{YELLOW}Push images to registry:{NC}")
    print(f"  podman tag myimage:latest {bridge_ip}:{REGISTRY_PORT}/myimage:latest")
    print(f"  podman push {bridge_ip}:{REGISTRY_PORT}/myimage:latest")
    print()
    print(f"{YELLOW}Test registry:{NC}")
    print(f"  curl http://{bridge_ip}:{REGISTRY_PORT}/v2/_catalog")
    print()
    print(f"{BLUE}╚═══════════════════════════════════════════════════════════╝{NC}")
    return 0


# ============================================================================
# VM Operations
# ============================================================================


def vm_build():
    """Build bootc disk image."""
    print(f"{BLUE}Building bootc disk image...{NC}")

    # Create output directory
    Path(DISK_PATH).parent.mkdir(parents=True, exist_ok=True)

    print(f"Building from: {IMAGE_REGISTRY}")
    print(f"Output: {DISK_PATH}")

    # Build disk image
    run_cmd([
        "sudo", "podman", "run", "--rm", "-it", "--privileged",
        "--pull=newer",
        "--security-opt", "label=type:unconfined_t",
        "-v", "/var/lib/containers/storage:/var/lib/containers/storage",
        "-v", f"{Path(DISK_PATH).parent}:/output",
        "-v", "./k8s/rke2/cloud-init.yaml:/config/cloud-init.yaml:ro",
        "quay.io/centos-bootc/bootc-image-builder:latest",
        "--type", "qcow2",
        "--rootfs", DISK_SIZE,
        IMAGE_REGISTRY
    ])

    # Move image to correct location
    qcow2_path = Path(DISK_PATH).parent / "qcow2" / "disk.qcow2"
    if qcow2_path.exists():
        subprocess.run(["sudo", "mv", str(qcow2_path), DISK_PATH], check=True)
        subprocess.run(["sudo", "rm", "-rf", str(qcow2_path.parent)], check=True)
        subprocess.run(["sudo", "chown", f"{os.getuid()}:{os.getgid()}", DISK_PATH], check=True)
        print(f"{GREEN}✓{NC} Disk image built: {DISK_PATH}")
        return 0
    else:
        print(f"{RED}✗{NC} Failed to build disk image")
        return 1


def vm_create():
    """Create VM from bootc image."""
    if is_vm_defined():
        print(f"{YELLOW}VM {VM_NAME} already exists{NC}")
        return 0

    print(f"{BLUE}Creating VM {VM_NAME}...{NC}")

    # Create shared directories
    for directory in [KUBECONFIG_DIR, STORAGE_DIR]:
        subprocess.run(["sudo", "mkdir", "-p", directory], check=True)
        subprocess.run(["sudo", "chmod", "755", directory], check=True)

    # Check if disk exists
    if not Path(DISK_PATH).exists():
        print(f"{RED}✗{NC} Disk image not found: {DISK_PATH}")
        print("Build it first with: rke2_ops.py vm build")
        return 1

    # Update XML template
    xml_template = Path("k8s/rke2/libvirt-domain.xml")
    if not xml_template.exists():
        print(f"{RED}✗{NC} libvirt-domain.xml not found")
        return 1

    xml_content = xml_template.read_text()
    xml_content = xml_content.replace("/var/lib/libvirt/images/rke2-node-1.qcow2", DISK_PATH)
    xml_content = xml_content.replace("/var/lib/libvirt/rke2/kubeconfig", KUBECONFIG_DIR)
    xml_content = xml_content.replace("/var/lib/libvirt/rke2/storage", STORAGE_DIR)
    xml_content = xml_content.replace("<name>rke2-node-1</name>", f"<name>{VM_NAME}</name>")

    tmp_xml = Path("/tmp/rke2-domain.xml")
    tmp_xml.write_text(xml_content)

    # Define VM
    subprocess.run(["sudo", "virsh", "define", str(tmp_xml)], check=True)
    tmp_xml.unlink()

    print(f"{GREEN}✓{NC} VM defined: {VM_NAME}")
    return 0


def vm_start():
    """Start the VM."""
    if not is_vm_defined():
        print(f"{RED}✗{NC} VM {VM_NAME} does not exist")
        print("Create it first with: rke2_ops.py vm create")
        return 1

    if is_vm_running():
        print(f"{YELLOW}VM {VM_NAME} is already running{NC}")
        return 0

    print(f"{BLUE}Starting VM {VM_NAME}...{NC}")
    subprocess.run(["sudo", "virsh", "start", VM_NAME], check=True)
    print(f"{GREEN}✓{NC} VM started")

    print("Waiting for VM to boot...")
    time.sleep(10)
    vm_get_ip()
    return 0


def vm_stop():
    """Stop the VM."""
    if not is_vm_running():
        print(f"{YELLOW}VM {VM_NAME} is not running{NC}")
        return 0

    print(f"{BLUE}Stopping VM {VM_NAME}...{NC}")
    subprocess.run(["sudo", "virsh", "shutdown", VM_NAME], check=True)
    print(f"{GREEN}✓{NC} VM shutdown initiated")
    return 0


def vm_restart():
    """Restart the VM."""
    vm_stop()
    time.sleep(5)
    return vm_start()


def vm_status():
    """Show VM status."""
    print(f"{BLUE}VM Status:{NC}")
    subprocess.run(["sudo", "virsh", "list", "--all"], check=False)

    if is_vm_running():
        print()
        print(f"{BLUE}VM Info:{NC}")
        subprocess.run(["sudo", "virsh", "dominfo", VM_NAME], check=False)

        print()
        print(f"{BLUE}Network:{NC}")
        subprocess.run(["sudo", "virsh", "domifaddr", VM_NAME], check=False)
    return 0


def vm_destroy():
    """Destroy VM (keeps disk)."""
    print(f"{BLUE}Destroying VM {VM_NAME}...{NC}")

    if is_vm_running():
        subprocess.run(["sudo", "virsh", "destroy", VM_NAME], check=False)

    subprocess.run(["sudo", "virsh", "undefine", VM_NAME], check=False)
    print(f"{GREEN}✓{NC} VM destroyed (disk preserved)")
    return 0


def vm_purge():
    """Purge VM and all data."""
    vm_destroy()

    print(f"{BLUE}Removing disk...{NC}")
    subprocess.run(["sudo", "rm", "-f", DISK_PATH], check=False)

    print(f"{BLUE}Removing shared directories...{NC}")
    subprocess.run(["sudo", "rm", "-rf", KUBECONFIG_DIR, STORAGE_DIR], check=False)

    print(f"{GREEN}✓{NC} VM purged")
    return 0


def vm_get_ip():
    """Get VM IP address."""
    print(f"{BLUE}Getting VM IP address...{NC}")
    time.sleep(5)

    result = run_cmd(
        ["sudo", "virsh", "domifaddr", VM_NAME],
        capture=True,
        check=False
    )

    for line in result.stdout.split("\n"):
        if "ipv4" in line:
            parts = line.split()
            for part in parts:
                if "/" in part and "." in part:
                    vm_ip = part.split("/")[0]
                    print(f"{GREEN}✓{NC} VM IP: {vm_ip}")
                    Path("/tmp/rke2-vm-ip").write_text(vm_ip)
                    return vm_ip

    print(f"{YELLOW}⚠{NC} Could not determine VM IP")
    print(f"Check with: sudo virsh domifaddr {VM_NAME}")
    return None


# ============================================================================
# Kubeconfig Operations
# ============================================================================


def get_kubeconfig():
    """Get kubeconfig from VM."""
    print(f"{BLUE}Checking for kubeconfig...{NC}")

    kubeconfig_file = Path(KUBECONFIG_DIR) / "rke2.yaml"

    if not kubeconfig_file.exists():
        print(f"{YELLOW}⚠{NC} Kubeconfig not found yet")
        print("Wait for RKE2 to start, then try again")
        return 1

    print(f"{GREEN}✓{NC} Kubeconfig found: {kubeconfig_file}")

    # Get VM IP
    vm_ip_file = Path("/tmp/rke2-vm-ip")
    if not vm_ip_file.exists():
        vm_ip = vm_get_ip()
    else:
        vm_ip = vm_ip_file.read_text().strip()

    if not vm_ip:
        print(f"{YELLOW}⚠{NC} Could not determine VM IP")
        return 1

    # Copy and update kubeconfig
    kube_dir = Path.home() / ".kube"
    kube_dir.mkdir(exist_ok=True)

    dest_config = kube_dir / "rke2-config"
    kubeconfig_content = kubeconfig_file.read_text()
    kubeconfig_content = kubeconfig_content.replace(
        "https://127.0.0.1:6443",
        f"https://{vm_ip}:6443"
    )
    dest_config.write_text(kubeconfig_content)

    print(f"{GREEN}✓{NC} Kubeconfig copied to {dest_config}")
    print()
    print("Use it with:")
    print(f"  export KUBECONFIG={dest_config}")
    print("  kubectl cluster-info")
    return 0


# ============================================================================
# Quickstart
# ============================================================================


def quickstart():
    """Run complete quickstart workflow."""
    print(f"{BLUE}╔═══════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║            RKE2 Quickstart Workflow                       ║{NC}")
    print(f"{BLUE}╚═══════════════════════════════════════════════════════════╝{NC}")
    print()

    steps = [
        ("Starting registry", registry_start),
        ("Building RKE2 bootc image", lambda: subprocess.run(["make", "rke2-build"]).returncode),
        ("Pushing to local registry", lambda: subprocess.run(["make", "rke2-push"]).returncode),
        ("Building VM disk image", vm_build),
        ("Creating VM", vm_create),
        ("Starting VM", vm_start),
        ("Waiting for RKE2 to start (120s)", lambda: time.sleep(120) or 0),
        ("Getting kubeconfig", get_kubeconfig),
    ]

    for i, (desc, func) in enumerate(steps, 1):
        print(f"{BLUE}==> Step {i}/{len(steps)}: {desc}...{NC}")
        if func() != 0:
            print(f"{RED}✗{NC} Step failed: {desc}")
            return 1

    print()
    print(f"{GREEN}╔═══════════════════════════════════════════════════════════╗{NC}")
    print(f"{GREEN}║          RKE2 Cluster Ready!                              ║{NC}")
    print(f"{GREEN}╚═══════════════════════════════════════════════════════════╝{NC}")
    print()
    print("Use your cluster with:")
    print(f"  export KUBECONFIG={Path.home()}/.kube/rke2-config")
    print("  kubectl get nodes")
    return 0


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="RKE2 Operations Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Registry commands
    registry_parser = subparsers.add_parser("registry", help="Manage container registry")
    registry_parser.add_argument(
        "action",
        choices=["start", "stop", "status", "info"],
        help="Registry action"
    )

    # VM commands
    vm_parser = subparsers.add_parser("vm", help="Manage virtual machines")
    vm_parser.add_argument(
        "action",
        choices=["build", "create", "start", "stop", "restart", "status", "destroy", "purge"],
        help="VM action"
    )

    # Kubeconfig command
    subparsers.add_parser("kubeconfig", help="Get kubeconfig from VM")

    # Quickstart command
    subparsers.add_parser("quickstart", help="Run complete quickstart workflow")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch commands
    if args.command == "registry":
        actions = {
            "start": registry_start,
            "stop": registry_stop,
            "status": registry_status,
            "info": registry_info,
        }
        return actions[args.action]()

    elif args.command == "vm":
        actions = {
            "build": vm_build,
            "create": vm_create,
            "start": vm_start,
            "stop": vm_stop,
            "restart": vm_restart,
            "status": vm_status,
            "destroy": vm_destroy,
            "purge": vm_purge,
        }
        return actions[args.action]()

    elif args.command == "kubeconfig":
        return get_kubeconfig()

    elif args.command == "quickstart":
        return quickstart()

    return 0


if __name__ == "__main__":
    sys.exit(main())
