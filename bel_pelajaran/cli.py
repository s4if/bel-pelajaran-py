import sys

from bel_pelajaran.check_config import check_config
from bel_pelajaran.check_sound import check_sound
from bel_pelajaran.database import (
    add_schedule,
    delete_schedule,
    get_available_sounds,
    get_schedule_by_id,
    list_schedules,
    update_schedule,
)
from bel_pelajaran.main import main as start_main


def cli():
    if len(sys.argv) < 2:
        print("Usage: bel <command> [args]")
        print("Commands:")
        print("  start [config.toml]   - Start the bell scheduler")
        print("  check <config.toml>   - Check configuration file")
        print("  check_sound           - Test sound playback")
        print("  list                  - List all schedules")
        print("  sounds                - List available sounds")
        print("  add <hari> <jam> <file> - Add a new schedule")
        print("  edit <id> [hari] [jam] [file] - Edit schedule")
        print("  delete <id>           - Delete schedule by ID")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "start":
        if len(args) > 0:
            sys.argv = ["bel"] + args
        start_main()
    elif command == "check":
        if len(args) < 1:
            print("Error: Please provide a config file")
            print("Usage: bel check <config.toml>")
            sys.exit(1)
        check_config(args[0])
    elif command == "check_sound":
        check_sound()
    elif command == "list":
        schedules = list_schedules()
        if not schedules:
            print("No schedules found.")
        else:
            print(
                "ID | Hari      | Jam   | File                      | Created At          | Edited At"
            )
            print(
                "---+-----------+-------+---------------------------+---------------------+---------------------"
            )
            for s in schedules:
                edited = s["edited_at"] if s["edited_at"] else "Never"
                print(
                    f"{s['id']:2d} | {s['hari']:9s} | {s['jam']:5s} | {s['file']:25s} | {s['created_at']:19s} | {str(edited):19s}"
                )
    elif command == "sounds":
        sounds = get_available_sounds()
        if not sounds:
            print("No sounds found in assets directory.")
        else:
            print("Available sounds:")
            for sound in sounds:
                print(f"  - {sound}")
    elif command == "add":
        if len(args) < 3:
            print("Error: Please provide hari, jam, and file")
            print("Usage: bel add <hari> <jam> <file>")
            print("Example: bel add senin '07:00' '1.mp3'")
            sys.exit(1)
        hari, jam, file = args[0], args[1], args[2]
        sounds = get_available_sounds()
        if file not in sounds:
            print(f"Error: Sound file '{file}' not found in assets.")
            print(f"Available sounds: {', '.join(sounds)}")
            sys.exit(1)
        schedule_id = add_schedule(hari, jam, file)
        print(f"Schedule added successfully with ID: {schedule_id}")
    elif command == "edit":
        if len(args) < 1:
            print("Error: Please provide schedule ID")
            print("Usage: bel edit <id> [hari] [jam] [file]")
            print("Example: bel edit 1 senin '08:00' '2.mp3'")
            print("Example: bel edit 1 senin")
            print("Example: bel edit 1 senin '08:00'")
            sys.exit(1)
        try:
            schedule_id = int(args[0])
        except ValueError:
            print("Error: ID must be a number")
            sys.exit(1)

        schedule = get_schedule_by_id(schedule_id)
        if not schedule:
            print(f"Error: Schedule with ID {schedule_id} not found")
            sys.exit(1)

        hari = args[1] if len(args) > 1 else None
        jam = args[2] if len(args) > 2 else None
        file = args[3] if len(args) > 3 else None

        if file:
            sounds = get_available_sounds()
            if file not in sounds:
                print(f"Error: Sound file '{file}' not found in assets.")
                print(f"Available sounds: {', '.join(sounds)}")
                sys.exit(1)

        update_schedule(schedule_id, hari=hari, jam=jam, file=file)
        print(f"Schedule {schedule_id} updated successfully")
    elif command == "delete":
        if len(args) < 1:
            print("Error: Please provide schedule ID")
            print("Usage: bel delete <id>")
            sys.exit(1)
        try:
            schedule_id = int(args[0])
        except ValueError:
            print("Error: ID must be a number")
            sys.exit(1)

        schedule = get_schedule_by_id(schedule_id)
        if not schedule:
            print(f"Error: Schedule with ID {schedule_id} not found")
            sys.exit(1)

        delete_schedule(schedule_id)
        print(f"Schedule {schedule_id} deleted successfully")
    else:
        print(f"Unknown command: {command}")
        print(
            "Available commands: start, check, check_sound, list, sounds, add, edit, delete"
        )
        sys.exit(1)


if __name__ == "__main__":
    cli()
