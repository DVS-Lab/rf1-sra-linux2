"""
XNAT download app, Caleb Haynes 2021; edited by Jeff Dennison 02 2022
req v python > 3.5 & xnat: python3 -m pip install xnat
usage: python3 downloadXNAT.py #Jeff hardcoded these for current purposes<url> <session> <outputDir>
log into xnat server, download scans
"""
import getpass
import os
import subprocess
import glob
import sys

try:
    import xnat
except ImportError:
    raise ImportError(
        """
        Module for XNAT not found- Run the following command:
        \n\n python3 -m pip install xnat"""
    )
os.umask(0)
#url = sys.argv[1]
#session = sys.argv[2]
#outputDir = sys.argv[3]
#subject = sys.argv[4]

url = "https://xnat.cla.temple.edu"
session = "Smith-SRA"
outputDir = "/ZPOOL/data/sourcedata/sourcedata/rf1-sra"

subs=os.listdir(outputDir)

def download_sub(url, session, outputDir):
    alias = os.getenv("XNAT_ALIAS")
    secret = os.getenv("XNAT_SECRET")
    with xnat.connect(url, user=alias, password=secret) as connect:
        for sub in connect.projects[session].subjects.values():
            if sub.label in subs:
                print("%s already retrieved from XNAT"%(sub.label))
            else:
                print("Downloading .. %s"%(sub.label))
                sub.download_dir(outputDir)
    return

download_sub(url, session, outputDir)
