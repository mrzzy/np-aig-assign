#
# NP AIG Assignment 1
# Utilities
#

from git import Repo


def get_mlflow_run_name():
    """
    Compute a mlflow run name using git describe
    """
    # use git describe to obtain commit description
    repo = Repo(search_parent_directories=True)
    commit_desc = repo.git.describe("--all", "--long", "--dirty")
    # strip "heads/" "tags/" prefix
    commit_desc = commit_desc.replace("heads/", "")
    commit_desc = commit_desc.replace("tags/", "")
    return commit_desc
