# GitHub Repository Setup Guide

This guide will help you publish this plugin to GitHub.

## Initial Repository Setup

### 1. Create GitHub Repository

1. Go to [GitHub](https://github.com) and log in
2. Click the "+" icon → "New repository"
3. Repository settings:
   - **Name**: `plex-media-server-manager-indigo`
   - **Description**: "Plex Media Server Manager plugin for Indigo Home Automation (Python 3)"
   - **Public** or **Private**: Your choice
   - **Initialize**: Don't add README, .gitignore, or license (we have them)
4. Click "Create repository"

### 2. Upload to GitHub

#### Option A: Using GitHub Desktop (Easiest)
1. Download and install [GitHub Desktop](https://desktop.github.com/)
2. File → Add Local Repository
3. Choose the `plex-media-server-manager-indigo` folder
4. Click "Publish repository"
5. Uncheck "Keep this code private" if you want it public
6. Click "Publish repository"

#### Option B: Using Command Line
```bash
cd plex-media-server-manager-indigo

# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Python 3 compatible version"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/plex-media-server-manager-indigo.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Creating a Release

### 1. Create a Tag
```bash
git tag -a v3.0.4-py3 -m "Python 3 compatible release"
git push origin v3.0.4-py3
```

### 2. Create GitHub Release
1. Go to your repository on GitHub
2. Click "Releases" → "Create a new release"
3. Fill in:
   - **Tag**: `v3.0.4-py3`
   - **Release title**: `v3.0.4-py3 - Python 3 Compatible`
   - **Description**: Copy from `releases/RELEASE_NOTES.md`
4. Upload the file from `releases/`:
   - `Plex Media Server Manager Python3.indigoPlugin.zip`
5. Click "Publish release"

## Repository Settings

### Topics/Tags
Add these topics to help people find your repository:
- `indigo-plugin`
- `plex`
- `home-automation`
- `python3`
- `indigo-domotics`
- `plex-media-server`

To add topics:
1. Go to your repository homepage
2. Click the gear icon next to "About"
3. Add topics in the "Topics" field

### README Display
GitHub will automatically display your README.md on the repository homepage.

## Maintaining the Repository

### When Making Updates
1. Make your changes
2. Test thoroughly
3. Update `CHANGELOG.md`
4. Commit changes:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```
5. Create new release (if version changes)

### Handling Issues
- GitHub Issues is enabled by default
- The templates in `.github/ISSUE_TEMPLATE/` will help users report issues
- Label issues appropriately (bug, enhancement, etc.)

### Pull Requests
- Review code carefully
- Test before merging
- Update CHANGELOG.md
- Thank contributors!

## Optional Enhancements

### Add GitHub Actions (CI/CD)
You could add automated testing, but this requires setting up a test environment.

### Add a License
Consider adding an appropriate open-source license:
- MIT License (permissive)
- Apache 2.0 (permissive with patent grant)
- GPL v3 (copyleft)

Check the original plugin's license and ensure compatibility.

### Add Screenshots
1. Create a `screenshots/` directory
2. Add screenshots of the plugin in action
3. Reference them in README.md:
   ```markdown
   ![Plugin Configuration](screenshots/config.png)
   ```

## Publicizing

Once published, you might want to:
1. Post on the [Indigo Forums](http://forums.indigodomo.com/)
2. Create an issue in the original plugin's repository (if it exists) linking to your Python 3 version
3. Update the Indigo Plugin Wiki (if there is one)

## Questions?

If you need help with GitHub, check their [documentation](https://docs.github.com/).
