# Using bootc-image-builder for Local Testing

## Overview

The `bootc-image-builder` tool allows you to convert your bootc container image into bootable disk images for testing without requiring CI/CD infrastructure. This is the recommended way to test your image locally before deploying.

## Installation

### Using Podman (Recommended)

The bootc-image-builder runs as a container, so no installation is needed beyond podman/docker:

```bash
# Verify podman is installed
podman --version
```

## Building Disk Images

### Quick Start

```bash
# Build your container image first
make build

# Generate a raw disk image for testing
sudo podman run \
    --rm \
    --privileged \
    --pull=newer \
    --security-opt label=type:unconfined_t \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    quay.io/centos-bootc/bootc-image-builder:latest \
    --type raw \
    --local \
    localhost:5000/exousia:latest
```

### Output Formats

The builder supports multiple output formats:

- `raw` - Raw disk image (for QEMU/KVM testing)
- `qcow2` - QCOW2 disk image (for libvirt/virt-manager)
- `vmdk` - VMware disk image
- `ami` - Amazon Machine Image
- `iso` - ISO installer image

Example with qcow2:

```bash
sudo podman run \
    --rm \
    --privileged \
    --pull=newer \
    --security-opt label=type:unconfined_t \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v $(pwd)/output:/output \
    quay.io/centos-bootc/bootc-image-builder:latest \
    --type qcow2 \
    --local \
    localhost:5000/exousia:latest
```

The output will be in `./output/qcow2/disk.qcow2`.

## Testing with Virtual Machines

### Using virt-manager

1. Build a qcow2 image:
```bash
mkdir -p ./output
sudo podman run \
    --rm \
    --privileged \
    --pull=newer \
    --security-opt label=type:unconfined_t \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v $(pwd)/output:/output \
    quay.io/centos-bootc/bootc-image-builder:latest \
    --type qcow2 \
    --local \
    localhost:5000/exousia:latest
```

2. Import into virt-manager:
   - Open virt-manager
   - Create New Virtual Machine
   - Choose "Import existing disk image"
   - Browse to `./output/qcow2/disk.qcow2`
   - Set OS to "Fedora 42" or similar
   - Allocate resources (4GB RAM, 2 CPUs recommended)
   - Complete the wizard

### Using QEMU directly

```bash
# Build raw image first
sudo podman run \
    --rm \
    --privileged \
    --pull=newer \
    --security-opt label=type:unconfined_t \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    -v $(pwd)/output:/output \
    quay.io/centos-bootc/bootc-image-builder:latest \
    --type raw \
    --local \
    localhost:5000/exousia:latest

# Boot with QEMU
qemu-system-x86_64 \
    -m 4096 \
    -smp 2 \
    -drive file=./output/raw/disk.raw,format=raw \
    -enable-kvm \
    -cpu host
```

## Testing on Physical Hardware

### Creating a Bootable USB

1. Build a raw image
2. Write to USB device:

```bash
# WARNING: This will erase the USB device!
# Replace /dev/sdX with your actual USB device
sudo dd if=./output/raw/disk.raw of=/dev/sdX bs=4M status=progress
sync
```

3. Boot from the USB device

## Best Practices

### Before Building

1. **Test container first**: Always run your container tests before building disk images
   ```bash
   make test
   ```

2. **Check image size**: Review your container image size to estimate disk space needed
   ```bash
   podman images localhost:5000/exousia
   ```

### During Development

1. **Use raw format for quick tests**: It's faster to build than qcow2
2. **Keep output directory**: Reuse VMs for iterative testing
3. **Test upgrades**: After changes, test `bootc upgrade` workflow
   ```bash
   # In the running VM
   sudo bootc upgrade
   sudo systemctl reboot
   ```

### Before Release

1. **Test all critical hardware**: WiFi, GPU, audio, etc.
2. **Verify user provisioning**: Ensure you can login with configured users
3. **Test application installation**: Verify Flatpak and package installs work
4. **Check Plymouth**: If enabled, verify boot splash displays correctly

## Troubleshooting

### Issue: "Permission denied" errors

**Solution**: Run with `sudo` or as root. The builder needs privileged access.

### Issue: Image build fails with "storage" errors

**Solution**: Ensure podman storage is accessible:
```bash
sudo chmod -R a+rX /var/lib/containers/storage
```

### Issue: Generated image doesn't boot

**Solution**: Check the container lint passed:
```bash
podman run --rm localhost:5000/exousia:latest bootc container lint
```

### Issue: Out of disk space

**Solution**: Clean up old builds:
```bash
rm -rf ./output
podman system prune -a
```

## Integration with CI/CD

The bootc-image-builder can be integrated into your CI/CD pipeline:

```yaml
- name: Build disk image for testing
  run: |
    sudo podman run \
      --rm \
      --privileged \
      --pull=newer \
      --security-opt label=type:unconfined_t \
      -v /var/lib/containers/storage:/var/lib/containers/storage \
      -v ${{ github.workspace }}/output:/output \
      quay.io/centos-bootc/bootc-image-builder:latest \
      --type qcow2 \
      --local \
      ${{ env.IMAGE_NAME }}:${{ github.sha }}
```

## References

- [bootc-image-builder GitHub](https://github.com/osbuild/bootc-image-builder)
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/)
- [Podman Desktop bootc Extension](https://github.com/podman-desktop/extension-bootc)

## See Also

- [TESTING.md](TESTING.md) - Container image testing
- [README.md](../README.md) - Project overview
