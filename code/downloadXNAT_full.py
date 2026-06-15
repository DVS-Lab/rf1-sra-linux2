"""
XNAT download app, Caleb Haynes 2021; edited by Jeff Dennison 02/2022
Edited by Melanie Kos, 04/2026

Requirements:
    python > 3.5
    xnat package: python3 -m pip install xnat

Usage:
    python3 downloadXNAT_full.py

Purpose:
    Modified veersion of the downloadXNAT.py or downloadXNAT_mk.py scripts

    Log into the Temple XNAT server and download all subjects in the Smith-SRA
    XNAT project to the local rf1-sra sourcedata directory.

    This version is intended for full project download/re-download use cases.
    For example, this is primarily used when Huiling reaches out about 
    clearing XNAT storage and asks you to confirm that you have all subject
    data stored locally. Running this with nohup or tmux is recommended as
    the downloads will likely take a full day. The script loops over every 
    subject available in the Smith-SRA XNAT project and attempts to download 
    each subject, regardless of whether a local subject directory or full 
    MR dataset for them already exists (which the standard version of the script
    does not do). 

Notes:
    Again, existing local files/directories are not explicitly checked or skipped by
    this script. Errors for individual subjects are printed, but do not stop the full loop.
    The script is to be run as-is, but note that the "session" and "outputDir" values can
    be amended for different projects.
"""

import getpass
import os

try:
    import xnat
except ImportError:
    raise ImportError(
        """
        Module for XNAT not found- Run the following command:
        
        python3 -m pip install xnat
        """
    )

os.umask(0)

url = "https://xnat.cla.temple.edu"
session = "Smith-SRA"
outputDir = "/ZPOOL/data/sourcedata/sourcedata/rf1-sra"


def download_sub(url, session, outputDir):
    user = input("Enter Your XNAT Username\n\n>> ")
    password = getpass.getpass("Enter Your XNAT Password\n\n>> ")

    with xnat.connect(url, user, password) as connect:
        for sub in connect.projects[session].subjects.values():
            print(f"Checking / downloading {sub.label}")

            try:
                sub.download_dir(outputDir)
                print(f"Finished {sub.label}")
            except Exception as e:
                print(f"Error downloading {sub.label}: {e}")

    return


download_sub(url, session, outputDir)

