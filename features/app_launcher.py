import subprocess
import os

# Application names and their launch commands
APP_COMMANDS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome",
    "vs code": "code",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe"
}

def open_application(app_name):
    
    app_name = app_name.lower().strip()
    
    if app_name not in APP_COMMANDS:
        return f"Sorry, I don't know how to open {app_name} yet."
    
    try:
        subprocess.Popen(APP_COMMANDS[app_name], shell=False)
        return f"Opening {app_name}. . ."
    except FileNotFoundError:
        return f"Could not find {app_name}. Please check whether it is installed or available in PATH. "
    except OSError as error:
        return f"Unable to open {app_name}: {error}"
