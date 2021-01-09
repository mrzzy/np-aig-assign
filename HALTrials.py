#
# NP AIG Assignment 1
# Run multiple trials of HAL and aggregate metrics
#

import os
import sys
import mlflow
import subprocess
import numpy as np
from tqdm import tqdm
from distutils.util import strtobool
from multiprocessing.pool import Pool
from tempfile import NamedTemporaryFile

from Globals import TEAM_NAME, PARAMS

## Experiment Settings
# no. of game trials to run for the experiment
N_TRIALS = os.environ.get("N_TRIALS", default=3)
# whether to return a non zero status if Team B/Red wins
RED_WIN_NONZERO_STATUS = bool(
    strtobool(os.environ.get("RED_WIN_NONZERO_STATUS", "False"))
)

# the name of the MLFlow experiment to log trial results to
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "np-aig-trials")

# config game params overrides documented in Global.py
RUN_ENV_OVERRIDES = {
    "REAL_TIME": "False",
    "HEADLESS": "True",
    "LOGGER": "NOPLogger",
    "CAMERA": "NOPCamera",
    "RED_WIN_NONZERO_STATUS": "False",
}


def run_trail(n_trail):
    """
    Run one trail of HAL and return result and scores of teams
    """
    # run game via subprocess as pygame does not handfe concurrency well
    hal_run = subprocess.run(
        [
            sys.executable,
            "HAL.py",
        ],
        env=RUN_ENV_OVERRIDES,
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


def print_results(scores, team_blue_wins, team_red_wins, file=sys.stdout):
    """
    Print out the results as a human readable report.
    """
    print("=" * 80, file=file)
    print(f"Best of {N_TRIALS} Trials:", file=file)
    if team_blue_wins > team_red_wins:
        print(f"Team {TEAM_NAME[0]} wins", file=file)
    elif team_red_wins > team_blue_wins:
        print(f"Team {TEAM_NAME[1]} wins", file=file)
    else:
        print(f"Team {TEAM_NAME[0]} & {TEAM_NAME[1]} draws", file=file)
    print(f"A wins/B wins: {team_blue_wins}-{team_red_wins}", file=file)

    # print individual match resources
    print("=" * 80, file=file)
    print("Results Report (A wins/ B wins):", file=file)
    for n_trial, score in zip(range(1, N_TRIALS + 1), scores):
        print(f"Trial {n_trial}: {score[0]}-{score[1]}", file=file)
    print("=" * 80, file=file)
    file.flush()


if __name__ == "__main__":
    # log trails to MLFlow
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(), Pool(processes=min(os.cpu_count() * 2, N_TRIALS)) as pool:
        # log trail parameters to Mlflow
        params = dict(PARAMS)
        params.update({k.lower(): v for k, v in RUN_ENV_OVERRIDES.items()})
        params.update(
            {
                "n_trails": N_TRIALS,
                "red_win_nonzero_status": RED_WIN_NONZERO_STATUS,
            }
        )
        mlflow.log_params(params)
        # run game trails
        scores = np.asarray(
            list(tqdm(pool.imap(run_trail, range(1, N_TRIALS + 1)), total=N_TRIALS))
        )

        for i_trail, score in zip(range(N_TRIALS), scores):
            # log scores for each trial
            mlflow.log_metrics(
                metrics={
                    f"team_{TEAM_NAME[0]}_score": score[0],
                    f"team_{TEAM_NAME[1]}_score": score[1],
                },
                step=i_trail,
            )

        # log game trial wins to MLFlow
        team_red_wins = np.sum(np.argmax(scores, axis=-1))
        team_blue_wins = N_TRIALS - team_red_wins
        team_blue_win_ratio, team_red_win_ratio = (
            team_blue_wins / N_TRIALS,
            team_red_wins / N_TRIALS,
        )
        mlflow.log_metrics(
            {
                f"team_{TEAM_NAME[0]}_wins": team_blue_wins,
                f"team_{TEAM_NAME[0]}_win_ratio": team_blue_win_ratio,
                f"team_{TEAM_NAME[1]}_wins": team_red_wins,
                f"team_{TEAM_NAME[1]}_win_ratio": team_red_win_ratio,
            },
        )

        # print results report
        print_results(scores, team_blue_wins, team_red_wins)
        with NamedTemporaryFile("w", suffix=".txt") as f:
            print_results(scores, team_blue_wins, team_red_wins, file=f)
            mlflow.log_artifact(f.name)

        # exit nonzero if red wins if configured to do so
        if RED_WIN_NONZERO_STATUS and team_red_wins > team_blue_wins:
            sys.exit(1)