# Zoros Environment Setup

This document explains how the zoros conda environment is configured and how to troubleshoot issues.

## Automatic Activation

The zoros environment should automatically activate when you:
1. Open Cursor in this project directory
2. Open a terminal in this project directory
3. Navigate to this project directory in an existing terminal

## Manual Activation

If automatic activation doesn't work, you can manually activate the environment:

```bash
# Option 1: Use the simple activation script
source scripts/environment/activate_zoros.sh

# Option 2: Use the full activation script
source scripts/environment/activate_env.sh

# Option 3: Manual activation
export CONDA_NO_PLUGINS=true
export PATH="/opt/homebrew/Caskroom/miniconda/base/envs/zoros/bin:$PATH"
export CONDA_DEFAULT_ENV=zoros
export CONDA_PREFIX="/opt/homebrew/Caskroom/miniconda/base/envs/zoros"
```

## Configuration Files

### Shell Configuration
- **~/.zshrc**: Contains `CONDA_NO_PLUGINS=true` to disable problematic conda plugins
- **scripts/environment/activate_env.sh**: Automatically activates the environment when in the project directory
- **scripts/environment/activate_zoros.sh**: Simple manual activation script

### Editor Configuration
- **.cursor/settings.json**: Cursor-specific settings for Python interpreter and environment
- **.vscode/settings.json**: VS Code settings (also works with Cursor)

## Troubleshooting

### Conda Activation Errors
If you see errors like:
```
TypeError: expected str, bytes or os.PathLike object, not NoneType
```

This is caused by the `anaconda_anon_usage` plugin. The fix is already applied:
1. `CONDA_NO_PLUGINS=true` is set in your shell configuration
2. Fallback activation methods are provided in the scripts

### Environment Not Activating
1. Make sure you're in the project directory
2. Restart your terminal/Cursor
3. Run `source scripts/environment/activate_zoros.sh` manually

### Python Packages Not Found
1. Verify the environment is activated: `echo $CONDA_DEFAULT_ENV` should show `zoros`
2. Check Python path: `which python` should show the zoros environment path
3. Reinstall packages if needed: `pip install -r requirements.txt`

## Testing the Setup

Run the setup script to test everything:

```bash
./scripts/environment/setup_environment.sh
```

This will:
- Make all scripts executable
- Test environment activation
- Verify key packages are available

## Key Environment Variables

- `CONDA_DEFAULT_ENV=zoros`
- `CONDA_PREFIX=/opt/homebrew/Caskroom/miniconda/base/envs/zoros`
- `CONDA_NO_PLUGINS=true`
- `PATH` includes the zoros environment's bin directory 