
from datetime import datetime
import ctypes
import subprocess

import psutil
from pycaw.pycaw import AudioUtilities


# -----------------------------
# TIME AND DATE
# -----------------------------

def get_time():
    return datetime.now().strftime("The current time is %I:%M %p.")


def get_date():
    return datetime.now().strftime("Today is %A, %d %B %Y.")


# -----------------------------
# BATTERY STATUS
# -----------------------------

def get_battery_status():
    battery = psutil.sensors_battery()

    if battery is None:
        return "Battery information is not available."

    percentage = battery.percent

    if battery.power_plugged:
        status = "Charging or connected to power."
    else:
        status = "Running on battery."

    return f"Battery is at {percentage} percent. {status}"


# -----------------------------
# VOLUME CONTROL
# -----------------------------

def get_audio_controller():
    device = AudioUtilities.GetSpeakers()

    if device is None:
        raise RuntimeError("No default audio output device found.")

    return device.EndpointVolume


def change_volume(amount):
    try:
        audio = get_audio_controller()

        current_volume = audio.GetMasterVolumeLevelScalar()
        new_volume = max(0.0, min(1.0, current_volume + amount))

        audio.SetMasterVolumeLevelScalar(new_volume, None)

        return f"Volume set to {round(new_volume * 100)} percent."

    except Exception as error:
        return f"Unable to change volume: {error}"


def mute_volume():
    try:
        audio = get_audio_controller()
        audio.SetMute(1, None)
        return "Volume muted."

    except Exception as error:
        return f"Unable to mute volume: {error}"


def unmute_volume():
    try:
        audio = get_audio_controller()
        audio.SetMute(0, None)
        return "Volume unmuted."

    except Exception as error:
        return f"Unable to unmute volume: {error}"


# -----------------------------
# WINDOWS CONTROL
# -----------------------------

def lock_computer():
    try:
        success = ctypes.windll.user32.LockWorkStation()

        if success:
            return "Locking your computer."

        return "Unable to lock your computer."

    except Exception as error:
        return f"Unable to lock computer: {error}"


def shutdown_computer():
    try:
        subprocess.run(
            ["shutdown", "/s", "/t", "30"],
            check=True
        )
        return "Shutdown scheduled in 30 seconds. Say cancel shutdown to stop it."

    except (OSError, subprocess.CalledProcessError) as error:
        return f"Unable to shut down computer: {error}"


def restart_computer():
    try:
        subprocess.run(
            ["shutdown", "/r", "/t", "30"],
            check=True
        )
        return "Restart scheduled in 30 seconds. Say cancel shutdown to stop it."

    except (OSError, subprocess.CalledProcessError) as error:
        return f"Unable to restart computer: {error}"


def cancel_shutdown():
    try:
        subprocess.run(
            ["shutdown", "/a"],
            check=True
        )
        return "Scheduled shutdown or restart cancelled."

    except (OSError, subprocess.CalledProcessError):
        return "No active shutdown or restart was found."
