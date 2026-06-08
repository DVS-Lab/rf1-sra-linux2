"""
XNAT download app, Caleb Haynes 2021; edited by Jeff Dennison 02 2022
Edited by MCK 4/2026
req v python > 3.5 & xnat: python3 -m pip install xnat
usage: python3 downloadXNAT.py
log into xnat server, download scans
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

