from features.app_launcher import open_application

from features.reminder import reminders

from features.app_closer import parse_close_command, close_application

from features.file_search import (
    search_files,
    open_folder,
    open_search_result
)

from features.system_control import (
    get_time,
    get_date,
    get_battery_status,
    change_volume,
    mute_volume,
    unmute_volume,
    lock_computer,
    shutdown_computer,
    restart_computer,
    cancel_shutdown
)


# Stores pending shutdown/restart confirmation
pending_action = None


def process_command(command):
    global pending_action

    command = command.lower().strip()

    # -----------------------------
    # REMINDERS
    # -----------------------------

    # The assistant asked for a reminder name: this reply is the name.
    if reminders.has_pending():
        return reminders.handle_name(command)

    if reminders.is_reminder_request(command):
        return reminders.start_request(command)

    if reminders.is_cancel_request(command):
        return reminders.cancel_all()

    # -----------------------------
    # CLOSE APPLICATIONS
    # -----------------------------

    close_request = parse_close_command(command)

    if close_request:
        target, force = close_request
        return close_application(target, force)

    # -----------------------------
    # BASIC COMMANDS
    # -----------------------------

    if command in ["hello", "hi", "hey"]:
        return "Hello! How can I help you?"

    elif command in ["help", "what can you do"]:
        return """
PERSONAL DESKTOP ASSISTANT

APPLICATIONS:
- Open Chrome
- Open VS Code
- Open Notepad
- Open Calculator
- Close Notepad
- Force close Chrome

FILE SEARCH:
- Find my resume
- Search Python projects
- Where is my resume
- Open result 1

FOLDERS:
- Open Desktop
- Open Documents
- Open Downloads
- Open Pictures

REMINDERS:
- Remind me in 5 minutes
- Remind me to drink water in 10 minutes
- Cancel reminders

SYSTEM CONTROL:
- What time is it
- What is today's date
- Battery status
- Volume up
- Volume down
- Mute volume
- Unmute volume
- Lock computer
- Shutdown
- Restart
- Cancel shutdown

EXIT:
- Exit
- Quit
- Bye
"""

    # -----------------------------
    # CONFIRMATION COMMANDS
    # -----------------------------

    elif command == "confirm shutdown":
        if pending_action == "shutdown":
            pending_action = None
            return shutdown_computer()

        return "There is no pending shutdown request."

    elif command == "confirm restart":
        if pending_action == "restart":
            pending_action = None
            return restart_computer()

        return "There is no pending restart request."

    elif command in ["cancel", "cancel shutdown"]:
        pending_action = None
        return cancel_shutdown()

    # -----------------------------
    # SYSTEM INFORMATION
    # -----------------------------

    elif command in ["time", "what time is it"]:
        return get_time()

    elif command in ["date", "what is today's date", "today's date"]:
        return get_date()

    elif command in ["battery", "battery status", "check battery"]:
        return get_battery_status()

    # -----------------------------
    # VOLUME CONTROL
    # -----------------------------

    elif command in ["volume up", "increase volume"]:
        return change_volume(0.10)

    elif command in ["volume down", "decrease volume"]:
        return change_volume(-0.10)

    elif command in ["mute", "mute volume"]:
        return mute_volume()

    elif command in ["unmute", "unmute volume"]:
        return unmute_volume()

    # -----------------------------
    # WINDOWS CONTROL
    # -----------------------------

    elif command in ["lock", "lock computer", "lock pc"]:
        return lock_computer()

    elif command in ["shutdown", "shut down", "shutdown computer"]:
        pending_action = "shutdown"
        return "Are you sure you want to shut down? Type confirm shutdown to proceed."

    elif command in ["restart", "restart computer"]:
        pending_action = "restart"
        return "Are you sure you want to restart? Type confirm restart to proceed."

    # -----------------------------
    # FILE SEARCH
    # -----------------------------

    elif command.startswith("open result "):
        try:
            index = int(command.replace("open result ", "", 1))
            return open_search_result(index)

        except ValueError:
            return "Please provide a valid result number."

    elif command.startswith("find "):
        return search_files(command[5:].strip())

    elif command.startswith("search "):
        return search_files(command[7:].strip())

    elif command.startswith("where is "):
        return search_files(command[9:].strip())

    # -----------------------------
    # OPEN APPLICATIONS / FOLDERS
    # -----------------------------

    elif command.startswith("open "):
        target = command[5:].strip()

        common_folders = [
            "desktop",
            "documents",
            "downloads",
            "pictures",
            "music",
            "videos"
        ]

        if target in common_folders:
            return open_folder(target)

        return open_application(target)

    elif command.startswith("launch "):
        return open_application(command[7:].strip())

    elif command.startswith("start "):
        return open_application(command[6:].strip())

    # -----------------------------
    # EXIT
    # -----------------------------

    elif command in ["exit", "quit", "bye"]:
        pending_action = None
        return "Goodbye!"

    else:
        return "Sorry, I don't understand that command."