# SDDM Themes Directory

This directory is used for automatically installing and configuring SDDM themes during image builds.

## Usage

1. **Drop theme bundles** into this directory:
   - Supported formats: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`
   - Theme bundles will be automatically extracted during build

2. **Theme structure** (inside the archive):
   ```
   theme-name/
   ├── metadata.desktop  (required)
   ├── Main.qml         (required)
   ├── theme.conf       (optional)
   └── assets/          (images, fonts, etc.)
   ```

3. **Automatic configuration**:
   - The `setup-sddm-themes` script will:
     - Extract all theme bundles to `/usr/share/sddm/themes/`
     - Set the first valid theme as default in `/etc/sddm.conf.d/99-theme.conf`

## Finding SDDM Themes

Popular SDDM themes can be found at:
- **KDE Store**: https://store.kde.org/browse?cat=101
- **GitHub**: Search for "sddm theme"
- **AUR** (for reference): Many themes available as examples

## Example Themes

Some popular SDDM themes:
- **Breeze**: Default KDE theme (included with KDE)
- **Sugar Dark**: https://github.com/MarianArlt/sddm-sugar-dark
- **Chili**: https://github.com/MarianArlt/sddm-chili
- **Aerial**: https://github.com/3ximus/aerial-sddm-theme

## Creating Theme Bundles

To create a theme bundle from a downloaded theme:

```bash
# From ZIP:
cp downloaded-theme.zip custom-configs/sddm/themes/

# From directory:
cd theme-directory
tar -czf ../theme-name.tar.gz .
cp ../theme-name.tar.gz /path/to/exousia/custom-configs/sddm/themes/
```

## Multiple Themes

You can include multiple theme bundles. The build script will:
- Extract all of them
- Set the **first** extracted theme as default
- Make all themes available for selection

To control which theme is default, name your preferred theme file alphabetically first
(e.g., `01-preferred-theme.tar.gz`, `02-alternative-theme.tar.gz`).

## Troubleshooting

If themes don't appear:
1. Verify the theme bundle contains `metadata.desktop` in the root theme directory
2. Check that the archive extracts to a single directory (not loose files)
3. Review build logs for extraction errors

## Manual Configuration

To change themes after installation, edit `/etc/sddm.conf.d/99-theme.conf`:

```ini
[Theme]
Current=your-theme-name
```

Or use the SDDM configuration GUI (if using KDE):
```bash
systemsettings5
# Navigate to: Startup and Shutdown > Login Screen (SDDM)
```
