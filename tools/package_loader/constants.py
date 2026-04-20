SUPPORTED_API_VERSIONS = {"exousia.packages/v1alpha1"}
SUPPORTED_KINDS = {
    "PackageBundle",
    "FeatureBundle",
    "PackageRemovalBundle",
    "PackageOverrideBundle",
    "KernelConfig",
    "KernelProfile",
}
DEFAULT_COMMON_BUNDLES = [
    "base-core",
    "base-media",
    "base-devtools",
    "base-rpm-packaging",
    "base-virtualization",
    "base-security",
    "base-network",
    "base-shell",
]
