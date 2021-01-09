#
# NP AIG Assignment 1
# Run multiple trials of HAL and aggregate metrics
#

import os
import sys
import subprocess
import numpy as np
from distutils.util import strtobool
from multiprocessing.pool import Pool

from Globals import TEAM_NAME

## Experiment Settings
# no. of game trials to run for the experiment
N_TRIALS = os.environ.get("N_TRIALS", default=2)
# whether to return a non zero status if Team B/Red wins
RED_WIN_NONZERO_STATUS = bool(
    strtobool(os.environ.get("RED_WIN_NONZERO_STATUS", "False"))
)


def run_trail(n_trail):
    """
    Run one trail of HAL and return result and scores of teams
    """
    # config game parameters documented in Global.py
    run_env = {
        "REAL_TIME": "False",
        "HEADLESS": "True",
        "LOGGER": "NOPLogger",
        "CAMERA": "NOPCamera",
        "RED_WIN_NONZERO_STATUS": "False",
    }

    # run game via subprocess as pygame does not handfe concurrency well
    hal_run = subprocess.run(
        [
            sys.executable,
            "HAL.py",
        ],
        env=run_env,
        capture_output=True,
    )
    if hal_run.returncode != 0:
        raise Exception(f"Unexpected exception running HAL:\n{hal_run.stderr}")

    # extract game score from game stdout
    out_lines = hal_run.stdout.decode("utf-8").splitlines()
    match_lines = [l for l in out_lines if "final score" in l.lower()]
    scores = [
        int(t) for t in match_lines[0].replace(":", "").split(" ") if str.isdigit(t)
    ]
    return scores


def print_results(scores, team_a_wins, team_b_wins, file=sys.stdout):
    # print out results report
    print("=" * 80, file=file)
    print(f"Best of {N_TRIALS} Trials:", file=file)
    if team_a_wins > team_b_wins:
        print(f"Team {TEAM_NAME[0]} wins", file=file)
    elif team_b_wins > team_a_wins:
        print(f"Team {TEAM_NAME[1]} wins", file=file)
    else:
        print(f"Team {TEAM_NAME[0]} & {TEAM_NAME[1]} draws", file=file)
    print("=" * 80, file=file)
    print("Results Report:")
    for n_trial, score in zip(range(1, N_TRIALS + 1), scores):
        print(f"Trial {n_trial}: {score[0]}-{score[1]}", file=file)
    print("=" * 80, file=file)


if __name__ == "__main__":
    with Pool(processes=min(os.cpu_count() * 2, N_TRIALS)) as pool:
        # run game trails
        scores = np.asarray(pool.map(run_trail, range(1, N_TRIALS + 1)))

    team_b_wins = np.sum(np.argmax(scores, axis=-1))
    team_a_wins = N_TRIALS - team_b_wins
    print_results(scores, team_a_wins, team_b_wins)
