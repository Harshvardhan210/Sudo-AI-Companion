from features.app_launcher import open_application

from features.reminder import reminders

from features.app_closer import parse_close_command, close_application

from features.web_tools import handle_web_command

from features.notes import notes, Reply

from features.todo import todos

from assistant.voice_input import strip_wake_word

from assistant.voice_output import (
    next_voice,
    set_voice_gender,
    change_speed
)

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

    original = command.strip()
    command = original.lower()

    # "sudo ..." can arrive with the wake word still attached (while taking
    # notes, or when typed). Keep both versions.
    heard_wake, without_wake = strip_wake_word(original)

    if heard_wake and not without_wake:
        return "Yes? Say your command."

    # -----------------------------
    # REMINDERS
    # -----------------------------

    # The assistant asked for a reminder name: this reply is the name.
    if reminders.has_pending():
        return reminders.handle_name(without_wake.lower() if heard_wake else command)

    # The assistant asked "What's the task?": this reply is the task.
    if todos.has_pending():
        return todos.handle_pending(without_wake if heard_wake else original)

    # -----------------------------
    # NOTES (add a note / open notes / save notes)
    # -----------------------------

    notes_response = notes.handle(original, heard_wake, without_wake)

    if notes_response is not None:
        # Only one card (notes or to-do) is shown on the left at a time.
        if notes.card_open and todos.card_open:
            todos.close_card()
        return notes_response

    # -----------------------------
    # TO-DO LIST (add task / show tasks / mark task done ...)
    # -----------------------------

    todo_response = todos.handle(original, heard_wake, without_wake)

    if todo_response is not None:
        if todos.card_open and notes.card_open:
            notes.close_card()
        return todo_response

    # From here on the wake word is not needed.
    if heard_wake:
        command = without_wake.lower().strip()

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
    # WEB: search, open website, play YouTube video
    # -----------------------------

    web_response = handle_web_command(command)

    if web_response is not None:
        return web_response

    # -----------------------------
    # ROBOT VOICE
    # -----------------------------

    if command in ["change voice", "next voice", "switch voice"]:
        return next_voice()

    if command in ["male voice", "use male voice", "switch to male voice",
                   "change to male voice", "use a male voice"]:
        return set_voice_gender("male")

    if command in ["female voice", "use female voice", "switch to female voice",
                   "change to female voice", "use a female voice"]:
        return set_voice_gender("female")

    if command in ["speak faster", "talk faster", "speed up"]:
        return change_speed(10)

    if command in ["speak slower", "talk slower", "slow down"]:
        return change_speed(-10)

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

TO-DO LIST:
- Add task buy milk
- Show my tasks
- Mark task 2 as done
- Delete task 3
- Clear completed tasks

NOTES:
- Add a note (then say each point)
- Open notes
- Save notes
- Delete last point
- Cancel notes

ROBOT VOICE:
- Change voice
- Male voice / Female voice
- Speak faster / Speak slower

WEB:
- Google python tutorials
- Search the web for best laptops
- Search YouTube for lofi music
- Play shape of you
- Open YouTube
- Open github.com
- Go to flipkart

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