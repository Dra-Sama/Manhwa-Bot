# Code By @V_Sbotmaker (on Telegram)

from os import path as ospath
from subprocess import run as srun

try:
        update = srun(
            [
                "git pull"
            ],
            shell=True,
        )
        
        if update.returncode == 0:
            print(f"Successfully updated with latest commit {UPSTREAM_BRANCH} from UPSTREAM_REPO")
        else:
            print("Something went wrong while updating, check UPSTREAM_REPO if valid or not!")
except Exception as err:
        print(err)
