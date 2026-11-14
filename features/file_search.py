
import os
from pathlib import Path


# Get the current user's home directory
HOME = Path.home()


# Folders where the assistant will search
SEARCH_LOCATIONS = [
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Downloads",
    HOME / "OneDrive" / "Desktop",
    HOME / "OneDrive" / "Documents",
]


# Directories to skip during searching
SKIP_FOLDERS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}


# Store the latest search results
LAST_SEARCH_RESULTS = []


# -----------------------------------
# SEARCH FILES AND FOLDERS
# -----------------------------------

def search_files(query, max_results=10):

    global LAST_SEARCH_RESULTS

    LAST_SEARCH_RESULTS = []

    query = query.lower().strip()

    # Remove unnecessary words
    stop_words = {"my", "the", "a", "an", "file", "folder"}

    keywords = [
        word for word in query.split()
        if word not in stop_words
    ]

    if not keywords:
        return "Please provide a file or folder name."

    results = []

    for location in SEARCH_LOCATIONS:

        if not location.exists():
            continue

        def handle_error(error):
            pass

        for root, dirs, files in os.walk(
            location,
            onerror=handle_error
        ):

            # Skip unnecessary directories
            dirs[:] = [
                folder for folder in dirs
                if folder.lower() not in SKIP_FOLDERS
                and not folder.startswith(".")
            ]

            # Search folder names
            for folder in dirs:

                if all(
                    keyword in folder.lower()
                    for keyword in keywords
                ):
                    results.append(Path(root) / folder)

            # Search file names
            for filename in files:

                if all(
                    keyword in filename.lower()
                    for keyword in keywords
                ):
                    results.append(Path(root) / filename)

            if len(results) >= max_results:
                break

        if len(results) >= max_results:
            break

    LAST_SEARCH_RESULTS = results

    if not results:
        return f"No results found for '{query}'."

    response = f"Found {len(results)} matching item(s):\n"

    for index, path in enumerate(results, start=1):

        item_type = "Folder" if path.is_dir() else "File"

        response += (
            f"\n{index}. [{item_type}] {path}"
        )

    response += "\n\nType 'open result 1' to open its location."

    return response


# -----------------------------------
# OPEN COMMON WINDOWS FOLDERS
# -----------------------------------

def open_folder(folder_name):

    folders = {
        "desktop": HOME / "Desktop",
        "documents": HOME / "Documents",
        "downloads": HOME / "Downloads",
        "pictures": HOME / "Pictures",
        "music": HOME / "Music",
        "videos": HOME / "Videos",
    }

    folder_name = folder_name.lower().strip()

    folder_path = folders.get(folder_name)

    if folder_path is None:
        return f"Unknown folder: {folder_name}"

    if not folder_path.exists():
        return f"Folder does not exist: {folder_path}"

    try:

        os.startfile(str(folder_path))

        return f"Opening {folder_name}."

    except OSError as error:

        return f"Unable to open folder: {error}"


# -----------------------------------
# OPEN SEARCH RESULT LOCATION
# -----------------------------------

def open_search_result(index):

    if not LAST_SEARCH_RESULTS:
        return "Please search for something first."

    if index < 1 or index > len(LAST_SEARCH_RESULTS):
        return "Invalid result number."

    path = LAST_SEARCH_RESULTS[index - 1]

    if not path.exists():
        return "This file or folder no longer exists."

    try:

        if path.is_dir():

            os.startfile(str(path))

        else:

            # Open the folder containing the file
            os.startfile(str(path.parent))

        return f"Opening location: {path}"

    except OSError as error:

        return f"Unable to open location: {error}"
