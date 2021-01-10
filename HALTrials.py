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
from statsmodels.stats.proportion import proportion_confint

from Globals import TEAM_NAME, PARAMS

## Experiment Settings
# no. of game trials to run for the experiment
N_TRIALS = int(os.environ.get("N_TRIALS", default=3))
# whether to return a non zero status if Team B/Red is significantly better at 95% confidence
RED_SIG_BETTER_NONZERO_STATUS = bool(
    strtobool(os.environ.get("RED_SIG_BETTER_NONZERO_STATUS", "False"))
)

# the name of the MLFlow experiment to log trial results to
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "np-aig-trials")

# config game params overrides documented in Global.py
RUN_ENV_OVERRIDES = {
    "REAL_TIME": "False",
    "HEADLESS": "True",
    "LOGGER": "NOPLogger",
    "CAMERA": "NOPCamera",
    "RED_SIG_BETTER_NONZERO_STATUS": "False",
}


def run_trial(n_trail):
    """
    Run one trial of HAL and return result and scores of teams
    """
    # run game via subprocess as pygame does not handfe concurrency well
    run_env = {**os.environ, **RUN_ENV_OVERRIDES}
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


def compute_statistics(scores):
    """
    Compute statistics from the given scores.
    """
    team_red_wins = np.sum(np.argmax(scores, axis=-1))
    team_blue_wins = N_TRIALS - team_red_wins
    # compute the proportion/ratio of wins
    team_blue_win_ratio, team_red_win_ratio = (
        team_blue_wins / N_TRIALS,
        team_red_wins / N_TRIALS,
    )
    # compute the 95% confidence interval of win proportion/ratio
    team_blue_95_ci = proportion_confint(
        team_blue_wins, N_TRIALS, alpha=1 - 0.95, method="normal"
    )
    team_red_95_ci = proportion_confint(
        team_red_wins, N_TRIALS, alpha=1 - 0.95, method="normal"
    )

    # perform hypothesis testing to determine which team is significantly better with 95% confidence
    # null hypothesis: team blue's NPCs is not significantly better/worse than team red's NPCs
    # alternative hypothesis: team blue's NPCs is significantly better/worse than team red's NPCs
    red_95_ci_lower, red_95_ci_upper = team_red_95_ci
    blue_95_ci_lower, blue_95_ci_upper = team_blue_95_ci
    if team_blue_win_ratio >= red_95_ci_upper:
        better_team_95 = "blue"
    elif team_red_win_ratio >= blue_95_ci_upper:
        better_team_95 = "red"
    else:
        better_team_95 = "draw"

    return {
        "team_blue_wins": team_blue_wins,
        "team_red_wins": team_red_wins,
        "team_blue_win_ratio": team_blue_win_ratio,
        "team_red_win_ratio": team_red_win_ratio,
        "team_blue_95_ci": team_blue_95_ci,
        "team_red_95_ci": team_red_95_ci,
        "better_team_95": better_team_95,
    }


def print_results(scores, stats, file=sys.stdout):
    """
    Print out the results as a human readable report.
    """
    print("=" * 80, file=file)
    print(f"Best of {N_TRIALS} Trials:", file=file)
    if stats["team_blue_wins"] > stats["team_red_wins"]:
        print(f"Team {TEAM_NAME[0]} wins", file=file)
    elif stats["team_red_wins"] > stats["team_blue_wins"]:
        print(f"Team {TEAM_NAME[1]} wins", file=file)
    else:
        print(f"Team {TEAM_NAME[0]} & {TEAM_NAME[1]} draws", file=file)
    print(
        f"{TEAM_NAME[0]} wins-{TEAM_NAME[1]} wins: {stats['team_blue_wins']}-{stats['team_red_wins']}",
        file=file,
    )
    # print out which team is better at 95% confidence
    if stats["better_team_95"] == "blue":
        print(
            f"Team {TEAM_NAME[0]} is significantly better @ 95% confidence", file=file
        )
    elif stats["better_team_95"] == "red":
        print(
            f"Team {TEAM_NAME[1]} is significantly better @ 95% confidence", file=file
        )
    else:
        print(
            f"Neither team {TEAM_NAME[0]} & {TEAM_NAME[1]} is significantly better @ 95% confidence",
            file=file,
        )

    # print win ratio and confidence it is better
    print(
        f"{TEAM_NAME[0]} win ratio: {stats['team_blue_win_ratio']} 95% CI {stats['team_blue_95_ci']}",
        file=file,
    )
    print(
        f"{TEAM_NAME[1]} win ratio: {stats['team_red_win_ratio']} 95% CI {stats['team_red_95_ci']}",
        file=file,
    )

    # print individual match resources
    print("=" * 80, file=file)
    print(f"Results Report ({TEAM_NAME[0]} wins-{TEAM_NAME[1]} wins):", file=file)
    for n_trial, score in zip(range(1, N_TRIALS + 1), scores):
        print(f"Trial {n_trial}: {score[0]}-{score[1]}", file=file)
    print("=" * 80, file=file)
    file.flush()


if __name__ == "__main__":
    # log trial to MLFlow
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(), Pool(processes=min(os.cpu_count() * 2, N_TRIALS)) as pool:
        # log trial parameters to Mlflow
        params = {
            **PARAMS,
            **{k.lower(): v for k, v in RUN_ENV_OVERRIDES.items()},
            **{
                "n_trial": N_TRIALS,
                "RED_SIG_BETTER_NONZERO_STATUS": RED_SIG_BETTER_NONZERO_STATUS,
            },
        }
        mlflow.log_params(params)
        # run game trial
        scores = np.asarray(
            list(tqdm(pool.imap(run_trial, range(1, N_TRIALS + 1)), total=N_TRIALS))
        )

        for i_trial, score in zip(range(N_TRIALS), scores):
            # log scores for each trial
            mlflow.log_metrics(
                metrics={
                    f"team_{TEAM_NAME[0]}_score": score[0],
                    f"team_{TEAM_NAME[1]}_score": score[1],
                },
                step=i_trial,
            )

        # log game trial wins to MLFlow
        stats = compute_statistics(scores)
        mlflow.log_metrics(
            {
                f"team_{TEAM_NAME[0]}_wins": stats["team_blue_wins"],
                f"team_{TEAM_NAME[0]}_win_ratio": stats["team_blue_win_ratio"],
                f"team_{TEAM_NAME[0]}_ci_lower_95": stats["team_blue_95_ci"][0],
                f"team_{TEAM_NAME[0]}_ci_upper_95": stats["team_blue_95_ci"][1],
                f"team_{TEAM_NAME[0]}_better_team_95": (
                    1 if stats["better_team_95"] == "blue" else 0
                ),
                f"team_{TEAM_NAME[1]}_wins": stats["team_red_wins"],
                f"team_{TEAM_NAME[1]}_win_ratio": stats["team_red_win_ratio"],
                f"team_{TEAM_NAME[1]}_95_ci_lower": stats["team_red_95_ci"][0],
                f"team_{TEAM_NAME[1]}_95_ci_upper": stats["team_red_95_ci"][1],
                f"team_{TEAM_NAME[1]}_better_team_95": (
                    1 if stats["better_team_95"] == "red" else 0
                ),
            },
        )

        # print results report
        print_results(scores, stats)
        with NamedTemporaryFile("w", prefix="results_report_", suffix=".txt") as f:
            print_results(scores, stats, file=f)
            mlflow.log_artifact(f.name)

    # exit nonzero status if red team is significantly better 95% confidence and configured to do so
    if RED_SIG_BETTER_NONZERO_STATUS and stats["better_team_95"] == "red":
        sys.exit(1)
