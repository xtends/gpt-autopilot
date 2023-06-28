import os
import sys
import copy
import time
import shutil
import signal
import subprocess

from helpers import yesno, safepath, codedir
import cmd_args

tasklist = []
tasklist_finished = True

clarification_asked = 0

# Implementation of the functions given to ChatGPT

def make_tasklist(tasks):
    global tasklist
    global tasklist_finished

    next_task = tasks.pop(0)
    all_tasks = ""

    all_tasks += "TASKLIST: 1. " + next_task + "\n"

    for number, item in enumerate(tasks):
        all_tasks += "          " + str( number + 2 ) + ". " + item + "\n"

    print(all_tasks, end="")

    if "use-tasklist" not in cmd_args.args and yesno("\nGPT: Do you want to continue with this task list?\nYou") != "y":
        modifications = input("\nGPT: What would you like to change?\nYou: ")
        print()
        return "Task list modification request: " + modifications

    print()

    if "one-task" in cmd_args.args:
        tasklist_finished = False
        return all_tasks + "\n\nPlease complete the project according to the above requirements"

    tasklist += tasks
    tasklist_finished = False

    print("TASK:     " + next_task)
    return "TASK_LIST_RECEIVED: Start with first task: " + next_task + ". Do all the steps involved in the task and only then run the task_finished function. If the task is already done in a previous task, you can call task_finished right away"

def file_open_for_writing(filename, content = ""):
    print(f"FUNCTION: Writing to file code/{filename}...")
    return f"Please respond in your next response with the full content of the file {filename}. Respond only with the contents of the file, no explanations. Create a fully working, complete file with no limitations on file size. Put file content between lines START_OF_FILE_CONTENT and END_OF_FILE_CONTENT. Start your response with START_OF_FILE_CONTENT"

def replace_text(find, replace, filename, count = -1):
    filename = safepath(filename)

    if ( len(find) + len(replace) ) > 37:
        print(f"FUNCTION: Replacing text in {codedir(filename)}...")
    else:
        print(f"FUNCTION: Replacing '{find}' with '{replace}' in {codedir(filename)}...")

    with open(codedir(filename), "r") as f:
        file_content = f.read()

    new_text = file_content.replace(find, replace, count)
    if new_text == file_content:
        print("ERROR:    Did not find text to replace")
        return "ERROR: Did not find text to replace"

    with open(codedir(filename), "w") as f:
        f.write(new_text)

    return "Text replaced successfully"

def file_open_for_appending(filename, content = ""):
    print(f"FUNCTION: Appending to file {codedir(filename)}...")
    return f"Please respond in your next response with the full text to append to the end of the file {filename}. Respond only with the contents to add to the end of the file, no explanations. Create a fully working, complete file with no limitations on file size. Put file content between lines START_OF_FILE_CONTENT and END_OF_FILE_CONTENT. Start your response with START_OF_FILE_CONTENT"

def read_file(filename):
    filename = safepath(filename)

    print(f"FUNCTION: Reading file {codedir(filename)}...")
    if not os.path.exists(codedir(filename)):
        print(f"ERROR:    File {filename} does not exist")
        return f"File {filename} does not exist"
    with open(codedir(filename), "r") as f:
        content = f.read()
    return f"The contents of '{filename}':\n{content}"

def create_dir(directory):
    directory = safepath(directory)

    print(f"FUNCTION: Creating directory {codedir(directory)}")
    if os.path.isdir(codedir(directory)):
        return "ERROR: Directory exists"
    else:
        os.mkdir(codedir(directory))
        return f"Directory {directory} created!"

def move_file(source, destination):
    source = safepath(source)
    destination = safepath(destination)

    print(f"FUNCTION: Move {codedir(source)} to {codedir(destination)}...")

    # Create parent directories if they don't exist
    parent_dir = os.path.dirname(codedir(destination))
    os.makedirs(parent_dir, exist_ok=True)

    try:
        shutil.move(codedir(source), codedir(destination))
    except:
        if os.path.isdir(codedir(source)) and os.path.isdir(codedir(destination)):
            return "ERROR: Destination folder already exists."
        return "Unable to move file."

    return f"Moved {source} to {destination}"

def copy_file(source, destination):
    source = safepath(source)
    destination = safepath(destination)

    print(f"FUNCTION: Copy {codedir(source)} to {codedir(destination)}...")

    # Create parent directories if they don't exist
    parent_dir = os.path.dirname(codedir(destination))
    os.makedirs(parent_dir, exist_ok=True)

    try:
        shutil.copy(codedir(source), codedir(destination))
    except:
        if os.path.isdir(codedir(source)) and os.path.isdir(codedir(destination)):
            return "ERROR: Destination folder already exists."
        return "Unable to copy file."

    return f"File {source} copied to {destination}"

def delete_file(filename):
    filename = safepath(filename)
    path = codedir(filename)

    print(f"FUNCTION: Deleting file {path}")

    if not os.path.exists(path):
        print(f"ERROR:    File {filename} does not exist")
        return f"ERROR: File {filename} does not exist"

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except:
        return "ERROR: Unable to remove file."

    return f"File {filename} successfully deleted"

def list_files(list = "", print_output = True):
    files_by_depth = {}
    directory = "code"

    for root, _, filenames in os.walk(directory):
        depth = str(root[len(directory):].count(os.sep))

        for filename in filenames:
            file_path = os.path.join(root, filename)
            if depth not in files_by_depth:
                files_by_depth[depth] = []
            files_by_depth[depth].append(file_path)

    files = []
    counter = 0
    max_files = 20
    for level in files_by_depth.values():
        for filename in level:
            counter += 1
            if counter > max_files:
                break
            files.append(filename)

    # Remove code folder from the beginning of file paths
    files = [file_path.replace("code/", "", 1).replace("code\\", "", 1) for file_path in files]

    if print_output: print(f"FUNCTION: Listing files in code directory")
    return f"The following files are currently in the project directory:\n{files}"

def ask_clarification(questions):
    global clarification_asked

    answers = ""

    for question in questions:
        if "\n" in question:
            answer = input(f"\nGPT:\n{question}\n\nYou: \n")
        else:
            answer = input(f"\nGPT: {question}\nYou: ")
        answers += f"Q: {question}\nA: {answer}\n"
        clarification_asked += 1

    print()

    return answers

def run_cmd(base_dir, command, reason, asynch=False):
    base_dir = safepath(base_dir)
    base_dir = base_dir.strip("/").strip("\\")

    if asynch == True:
        asynchly = " asynchronously"
    else:
        asynchly = ""

    print()
    print(f"GPT: I want to run the following command{asynchly}:")

    the_dir = os.path.join("code", base_dir)
    command = "cd " + the_dir + "; " + command
    print("------------------------------")
    print(f"{command}")
    print("------------------------------")
    print(reason)
    print()

    if asynch == True:
        print("#################################################")
        print("# WARNING: This command will run asynchronously #")
        print("# and it will not be automatically killed after #")
        print("# GPT-AutoPilot is closed. You must close the   #")
        print("# program manually afterwards!                  #")
        print("#################################################")
        print()

    answer = yesno(
        "Do you want to run this command?",
        ["YES", "NO", "ASYNC", "SYNC"]
    )
    print()

    if answer == "ASYNC":
        asynch = True
        answer = "YES"

    elif answer == "SYNC":
        asynch = False
        answer = "YES"

    if answer == "YES":
        process = subprocess.Popen(
            command + " > gpt-autopilot-cmd-outout.txt 2>&1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Run command asynchronously in the background
        if asynch:
            # Wait for 4 seconds
            time.sleep(4)
        else:
            try:
                # Wait for the subprocess to finish
                process.wait()
            except KeyboardInterrupt:
                # Send Ctrl+C signal to the subprocess
                process.send_signal(signal.SIGINT)

        # read possible output
        output_file = os.path.join(the_dir, "gpt-autopilot-cmd-outout.txt")
        with open(output_file) as f:
            output = f.read()
        os.remove(output_file)

        return_value = "Result from command (first 400 chars):\n" + output[:400]

        if len(output) > 400:
            return_value += "\nResult from command (last 245 chars):\n" + output[-245:]

        if output.strip() == "":
            return_value += "<no output from command>"

        return_value = return_value.strip()

        print(return_value)
        print()

        return return_value
    else:
        return "I don't want to run that command"

def project_finished(finished=True):
    global tasklist_finished
    tasklist_finished = True
    return "PROJECT_FINISHED"

def task_finished(finished=True):
    global tasklist

    print("FUNCTION: Task finished")

    if len(tasklist) > 0:
        next_task = tasklist.pop(0)
        print("TASK:     " + next_task)
        return "Thank you. Please do the next task: " + next_task

    tasklist_finished = True
    return "PROJECT_FINISHED"

# Function definitions for ChatGPT

make_tasklist_func = {
    "name": "make_tasklist",
    "description": """
Convert the next steps to be taken into a list of tasks and pass them as a list into this function. Don't add already done tasks.

Remember that the tasklist should be able to be completed with simple file
operations or terminal commands, so don't include anything that can't be
accomplished using these methods (e.g. checking a UI or running tests)

For a trivial task, make just one task
""",
    "parameters": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "description": "The task list",
            },
        },
        "required": ["tasks"],
    },
}

ask_clarification_func = {
    "name": "ask_clarification",
    "description": "Ask the user clarifying question(s) about the project that are needed to implement it properly",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "A list of clarifying questions for the user",
            },
        },
        "required": ["questions"],
    },
}

definitions = [
    make_tasklist_func,
    {
        "name": "list_files",
        "description": "List the files in the current project",
        "parameters": {
            "type": "object",
            "properties": {
                "list": {
                    "type": "string",
                    "description": "Set always to 'list'",
                },
            },
            "required": ["list"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file with given name. Returns the file contents as string.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to read",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "file_open_for_writing",
        "description": "Open a file for writing. Existing files will be overwritten. Parent directories will be created if they don't exist. Content of file will be asked in the next prompt.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to write to",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "replace_text",
        "description": "Replace text in given file",
        "parameters": {
            "type": "object",
            "properties": {
                "find": {
                    "type": "string",
                    "description": "The text to look for",
                },
                "replace": {
                    "type": "string",
                    "description": "The text to replace the occurences with",
                },
                "filename": {
                    "type": "string",
                    "description": "The name of file to modify",
                },
                "count": {
                    "type": "number",
                    "description": "The number of occurences to replace (default = all occurences)",
                },
            },
            "required": ["find", "replace", "filename"],
        },
    },
    {
        "name": "file_open_for_appending",
        "description": "Open a file for appending content to the end of a file with given name (after the last line). The content to append will be given in the next prompt",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to append to",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "move_file",
        "description": "Move a file from one place to another. Parent directories will be created if they don't exist",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The source file to move",
                },
                "destination": {
                    "type": "string",
                    "description": "The new filename / filepath",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "create_dir",
        "description": "Create a directory with given name",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Name of the directory to create",
                },
            },
            "required": ["directory"],
        },
    },
    {
        "name": "copy_file",
        "description": "Copy a file from one place to another. Parent directories will be created if they don't exist",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The source file to copy",
                },
                "destination": {
                    "type": "string",
                    "description": "The new filename / filepath",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "delete_file",
        "description": "Deletes a file with given name",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to delete",
                },
            },
            "required": ["filename"],
        },
    },
    ask_clarification_func,
    {
        "name": "project_finished",
        "description": "Call this function when the whole project is finished",
        "parameters": {
            "type": "object",
            "properties": {
                "finished": {
                    "type": "boolean",
                    "description": "Set this to true always",
                },
            },
            "required": ["finished"],
        },
    },
    {
        "name": "task_finished",
        "description": "Call this function when a task from the tasklist has been finished",
        "parameters": {
            "type": "object",
            "properties": {
                "finished": {
                    "type": "boolean",
                    "description": "Set this to true always",
                },
            },
            "required": ["finished"],
        },
    },
    {
        "name": "run_cmd",
        "description": "Run a terminal command. Returns the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "base_dir": {
                    "type": "string",
                    "description": "The directory to change into before running command",
                },
                "command": {
                    "type": "string",
                    "description": "The command to run",
                },
                "reason": {
                    "type": "string",
                    "description": "A reason for why the command should be run",
                },
                "asynch": {
                    "type": "boolean",
                    "description": "Whether to run the program asynchronously (in the background)",
                },
            },
            "required": ["base_dir", "command", "reason"],
        },
    },
]

def get_definitions(model):
    global definitions

    func_definitions = copy.deepcopy(definitions)

    # gpt-3.5 is not responsible enough for these functions
    gpt3_disallow = [
        "create_dir",
        "move_file",
        "copy_file",
        "replace_text",
    ]

    if "gpt-4" not in model:
        func_definitions = [definition for definition in func_definitions if definition["name"] not in gpt3_disallow]

    if "no-tasklist" in cmd_args.args:
        func_definitions = [definition for definition in func_definitions if definition["name"] != "make_tasklist"]

    if "no-questions" in cmd_args.args:
        func_definitions = [definition for definition in func_definitions if definition["name"] != "ask_clarification"]

    return func_definitions
