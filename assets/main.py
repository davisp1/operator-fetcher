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
STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.DEBUG)
STDOUT_HANDLER.setFormatter(formatter)
LOGGER.addHandler(STDOUT_HANDLER)

# Path to fetch operators repositories
FETCH_OP_PATH = "fetch-op"

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


def extract_repo_name(url):
    """
    Extract the repository name from the url
    (commonly the last part of the URL without ".git" suffix and "op-" prefix)
    """

    return url.split("/")[-1].replace(".git", "").replace("op-", "")


def check_op_validity(op_name):
    """
    Check operator repository validity
    """

    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir("%s/op-%s" % (FETCH_OP_PATH, op_name)):
        if pattern.match(file_path):
            break
    else:
        LOGGER.warning("[%s] No catalog file found.", op_name)

    # Check if subfolder containing operator exists
    if not os.path.isdir("%s/op-%s/%s" % (FETCH_OP_PATH, op_name, op_name)):
        raise Exception("[%s] sub-folder op-%s/%s not found",
                        op_name, op_name, op_name)


# Read repositories list
REPO_LIST = read_list()


def fetch_repo(repository_info):
    # Extract name from repository
    url = repository_info.get('url')
    op_name = extract_repo_name(url)
    reference = repository_info.get('ref', 'master')
    extract_to_path = "%s/op-%s" % (FETCH_OP_PATH, op_name)
    commit_ref = "no_info"
    LOGGER.debug("[%s] Processing ...", op_name)

    if url[0] == "/":
        # Repository is a local path
        try:
            shutil.rmtree("%s/%s" % (FETCH_OP_PATH, op_name),
                          ignore_errors=True)
            shutil.copytree(url, "%s/op-%s" % (FETCH_OP_PATH, op_name))
            commit_ref = "local_changes"
        except Exception as e:
            LOGGER.warning(
                "[%s] Can't copy from path %s.\n%s", op_name, url, e)
    else:
        # Repository is a url path

        # If repo already exists, check if there is any change
        try:
            repo = git.Repo(extract_to_path)
            remote_ref = git_remote_ref(url, reference)
            if str(repo.head.commit) == remote_ref:
                # No change since the last run
                LOGGER.info("[%s] No changes detected" % op_name)
            else:
                # Update HEAD to required reference
                LOGGER.info("[%s] Change detected (%s -> %s)",
                            op_name, str(repo.head.commit), remote_ref)
                repo.remotes[0].fetch()
                repo.head.reference = repo.commit(reference)

        except git.exc.BadName:
            LOGGER.warning("[%s] Reference %s is not valid. Keeping current reference." % (
                op_name, reference))
        except git.exc.NoSuchPathError:
            LOGGER.info("[%s] New operator detected", op_name)

            # Clone repository
            try:
                repo = git.Repo.clone_from(
                    url=url,
                    to_path=extract_to_path,
                    branch=reference)
                commit_ref = str(repo.commit())
            except Exception as ex:
                LOGGER.warning("[%s] Impossible to clone: \n%s", url, ex)
                return
        except Exception as ex:
            LOGGER.warning("[%s] Unknown exception: \n%s", url, ex)
            return

    # Consistency check
    try:
        check_op_validity(op_name)
    except Exception:
        return

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
    shutil.rmtree("%s/%s" % (OP_PATH, op_name),
                  ignore_errors=True)
    shutil.copytree("%s/op-%s/%s" % (FETCH_OP_PATH, op_name, op_name),
                    "%s/%s" % (OP_PATH, op_name),
                    ignore=ignored)
    if os.path.exists("%s/op-%s/LICENSE" % (FETCH_OP_PATH, op_name)):
        shutil.copy("%s/op-%s/LICENSE" % (FETCH_OP_PATH, op_name),
                    "%s/%s/" % (OP_PATH, op_name))
    if os.path.exists("%s/op-%s/README.md" % (FETCH_OP_PATH, op_name)):
        shutil.copy("%s/op-%s/README.md" % (FETCH_OP_PATH, op_name),
                    "%s/%s/" % (OP_PATH, op_name))
    if os.path.exists("%s/op-%s/*.json" % (FETCH_OP_PATH, op_name)):
        shutil.copy("%s/op-%s/*.json" % (FETCH_OP_PATH, op_name),
                    "%s/%s/" % (OP_PATH, op_name))

    repository_info["commit"] = commit_ref
    return repository_info


results = []
with Pool(4) as p:
    # Fetch repositories
    results = p.map(fetch_repo, REPO_LIST)

# Strip failed jobs
results = [x for x in results if x is not None]

# Create Operators Version manifest
with open("%s/versions.yml" % OP_PATH, 'w') as output_stream:
    yaml.dump(results, output_stream, default_flow_style=False)

# Remove the unneeded repositories
repo_list_build = [extract_repo_name(x["url"]) for x in results]
repo_list_build.append("versions.yml")
for operator_path in os.listdir(FETCH_OP_PATH):
    operator_name = operator_path.replace('op-', '')
    if operator_name not in repo_list_build:
        shutil.rmtree("%s/%s" % (OP_PATH, operator_name),
                      ignore_errors=True)
        shutil.rmtree("%s/op-%s" % (FETCH_OP_PATH, operator_name),
                      ignore_errors=True)
        LOGGER.info("[%s] removed (unused for this run)", operator_name)


def show_summary():
    """
    Display summary as debug
    """
    with open("%s/versions.yml" % OP_PATH, 'r') as f:
        for line in f:
            LOGGER.debug(line.rstrip('\n'))


show_summary()
