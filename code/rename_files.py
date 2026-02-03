import os

# ------------------ SETTINGS ------------------
directory = "."      # folder with your files
dry_run = False       # set to False to actually rename
# ----------------------------------------------

# Hard-coded mapping: old_number -> new_number
mapping = {
    2: 23,
    3: 24,
    4: 25,
    5: 26,
    6: 27,
    7: 28,
    8: 29,
    10: 30,
    11: 31,
    12: 32,
    13: 33,
    15: 34,
    16: 35,
    17: 36,
    18: 37,
    19: 38,
    20: 39,
    21: 40,
    23: 41,
    24: 42,
    25: 43,
    26: 44,
    28: 45,
    29: 46,
    30: 47,
    31: 48,
    32: 49,
    34: 50,
    35: 51,
    36: 52,
    38: 53,
    39: 54,
}

# Rename files
for filename in os.listdir(directory):
    for old, new in mapping.items():
        prefix = f"{old}-"
        if filename.startswith(prefix):
            new_name = f"{new}-" + filename[len(prefix):]

            if dry_run:
                print(f"[DRY RUN] {filename} -> {new_name}")
            else:
                os.rename(
                    os.path.join(directory, filename),
                    os.path.join(directory, new_name)
                )
                print(f"Renamed: {filename} -> {new_name}")

print("Done.")
