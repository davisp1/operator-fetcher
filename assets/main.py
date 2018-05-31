#!/bin/python3

import yaml
import git
import os
import shutil
import re
import logging
from multiprocessing import Pool

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
# Create another handler that will redirect log entries to STDOUT
STREAM_HANDLER = logging.StreamHandler()
STREAM_HANDLER.setLevel(logging.DEBUG)
STREAM_HANDLER.setFormatter(formatter)
LOGGER.addHandler(STREAM_HANDLER)

# Path to fetch operators repositories
FETCH_OP_PATH = "raw-op"

# Path to prepared operators
OP_PATH = "op"


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

# Cleanup & Prepare workspace
if os.path.exists(OP_PATH):
    shutil.rmtree(OP_PATH, ignore_errors=True)
if os.path.exists(FETCH_OP_PATH):
    shutil.rmtree(FETCH_OP_PATH, ignore_errors=True)
os.makedirs(FETCH_OP_PATH)


def fetch_repo(repository_info):
    # Extract name from repository
    url = repository_info.get('url')
    repo_name = url.split("/")[-1].replace(".git", "")
    LOGGER.info("Fetching %s" % repo_name)
    # Clone repository
    try:
        repo = git.Repo.clone_from(
            url=url,
            to_path="%s/%s" % (FETCH_OP_PATH, repo_name),
            branch=repository_info.get('ref', 'master'))
    except git.exc.GitCommandError as ex:
        LOGGER.warning("Impossible to clone %s" % url, ex)
        return

    # Consistency check
    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir("%s/%s" % (FETCH_OP_PATH, repo_name)):
        if pattern.match(file_path):
            break
    else:
        LOGGER.warning(
            "No catalog file found for [%s] (url: %s)" % (repo_name, url))

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
