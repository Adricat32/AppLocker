import csv
import os
import subprocess

from interfaz import AppLockerWindow


def close_previous_instances() -> None:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq AppLocker.exe", "/FO", "CSV", "/NH"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) < 2 or row[0].lower() != "applocker.exe":
            continue
        try:
            process_id = int(row[1])
        except ValueError:
            continue
        if process_id != os.getpid():
            subprocess.run(
                ["taskkill", "/F", "/PID", str(process_id)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    close_previous_instances()
    AppLockerWindow().mainloop()
