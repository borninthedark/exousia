# YAML Definitions

Alternative build blueprints for different image variants.

## Blueprints

| File | Image Type |
|------|-----------|
| `sway-bootc.yml` | Full bootc image with Sway desktop |
| `sway-atomic.yml` | Fedora Sway Atomic base |

The primary blueprint is `adnyeus.yml` in the repository root.
These definitions provide pre-configured variants that can be passed
to the transpiler directly.

## Usage

```bash
uv run python tools/yaml-to-containerfile.py \
  --config yaml-definitions/sway-bootc.yml \
  --output Containerfile.generated
```

## See Also

- [Blueprint](../adnyeus.yml) -- Primary build configuration
- [Build Tools](../tools/) -- Transpiler documentation
