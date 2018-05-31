#!/bin/python3

import yaml
import git
import os
import sys
import shutil
import re
import logging
from multiprocessing import Pool

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

# Create another handler that will redirect log entries to STDOUT
STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.DEBUG)
STDOUT_HANDLER.setFormatter(formatter)
LOGGER.addHandler(STDOUT_HANDLER)

# Create another handler that will redirect Warning entries to STDERR
STDERR_HANDLER = logging.StreamHandler(sys.stderr)
STDERR_HANDLER.setLevel(logging.WARNING)
STDERR_HANDLER.setFormatter(formatter)
LOGGER.addHandler(STDERR_HANDLER)

# Path to fetch operators repositories
FETCH_OP_PATH = "raw-op"

# Path to prepared operators
OP_PATH = "op"


def git_remote_ref(url, reference):
    """
    Equivalent to git ls-remote function but returns only the sha1 of the remote reference
    """
    g = git.cmd.Git()
    return g.ls_remote(url, reference).split('\n')[0].split('\t')[0]


def read_list():
    """
    Reads the repo-list.yml file to get the url to operators
    :return: the dict containing the yaml information
    """
    with open("repo-list.yml", 'r') as input_stream:
        repositories = yaml.load(input_stream)
        return repositories


# Read repositories list
REPO_LIST = read_list()


def fetch_repo(repository_info):
    # Extract name from repository
    url = repository_info.get('url')
    repo_name = url.split("/")[-1].replace(".git", "")
    reference = repository_info.get('ref', 'master')
    extract_to_path = "%s/%s" % (FETCH_OP_PATH, repo_name)
    LOGGER.info("[%s] Processing ...", repo_name)

    # If repo already exists, check if there is any change
    try:
        repo = git.Repo(extract_to_path)
        remote_ref = git_remote_ref(url, reference)
        if str(repo.head.commit) == remote_ref:
            # No change since the last run
            LOGGER.info("[%s] No changes detected" % repo_name)
        else:
            # Update HEAD to required reference
            LOGGER.info("[%s] Change detected (%s -> %s)",
                        repo_name, str(repo.head.commit), remote_ref)
            repo.remotes[0].fetch()
            repo.head.reference = repo.commit(reference)
    except git.exc.NoSuchPathError:
        LOGGER.info("[%s] New operator detected", repo_name)

        # Clone repository
        try:
            repo = git.Repo.clone_from(
                url=url,
                to_path=extract_to_path,
                branch=reference)
        except git.exc.GitCommandError as ex:
            LOGGER.warning("[%s] Impossible to clone: \n%s", url, ex)
            return

    # Consistency check
    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir("%s/%s" % (FETCH_OP_PATH, repo_name)):
        if pattern.match(file_path):
            break
    else:
        LOGGER.warning(
            "[%s] No catalog file found. (url: %s)" % (repo_name, url))

    # Copy sources to build path
    ignored_patterns = [
        ".git",
        "test",
        "test/",
        "tests",
        "tests/",
        "test_*.py",
        "tests_*.py",
        "catalog_def*.json"
    ]
    ignored = shutil.ignore_patterns(*ignored_patterns)
    shutil.copytree("%s/%s" % (FETCH_OP_PATH, repo_name), "%s/%s" %
                    (OP_PATH, repo_name), ignore=ignored)

    repository_info["commit"] = str(repo.commit())
    return repository_info


# Fetch repositories
with Pool(4) as p:
    results = p.map(fetch_repo, REPO_LIST)

    # Create Operators Version manifest
    with open("%s/versions.yml" % OP_PATH, 'w') as output_stream:
        yaml.dump(results, output_stream, default_flow_style=False)

# Display the content
with open("%s/versions.yml" % OP_PATH, 'r') as f:
    for line in f:
        LOGGER.debug(line.rstrip('\n'))