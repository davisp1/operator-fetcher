#!/bin/python3

import yaml
import os
import shutil
import re
import glob
import logging
import importlib
import subprocess
from multiprocessing import Pool

catalog = importlib.import_module('catalog')

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

# Create another handler that will redirect log entries to STDOUT
STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.DEBUG)
STDOUT_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(STDOUT_HANDLER)

# Max number of simultaneous repositories connections
SIMULTANEOUS_CONNECTIONS = 15

# Path to fetch operators repositories
CACHE_PATH = "/app/fetch-op"

# Path to prepared operators
OP_PATH = "op"

# Path to families list
FAM_PATH = "fam"

# firstly provides families.json to shared volume
if not os.path.exists(FAM_PATH):
    os.mkdir(FAM_PATH)
try:
    os.remove("%s/families.json" % FAM_PATH)
except FileNotFoundError:
    pass
finally:
    shutil.copy("families.json", FAM_PATH)


def extract_repo_name(url):
    """
    Extract the repository name from the url
    (commonly the last part of the URL without ".git" suffix and "op-" prefix)
    """
    return url.split("/")[-1].replace(".git", "").replace("op-", "")


def get_yaml_content(yaml_file):
    """
    Reads the yaml file and return the corresponding dict
    :return: the dict containing the yaml information
    """
    with open(yaml_file, 'r') as input_stream:
        return yaml.load(input_stream)


def check_op_validity(repo_path, url):
    """
    Check operator repository validity
    """

    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir(repo_path):
        if pattern.match(file_path):
            break
    else:
        LOGGER.warning("[%s] No catalog file found.", url)


# Read repositories list
REPO_LIST = get_yaml_content("/app/repo-list.yml")


def get_repo_path(url):
    """
    URL is unique so use it to know where is the path of the cache
    """
    return subprocess.run(['bash', 'getMatchingCacheRepo.sh', CACHE_PATH, url], stdout=subprocess.PIPE).stdout


def fetch_repo(repository_info):
    """
    Fetch the repository to the cache and build the operators list
    """

    # Extract name from repository
    url = repository_info.get('url',"no_url")
    reference = repository_info.get('ref')

    LOGGER.debug("Processing %s", url)

    # Update cache to the required reference
    cmd_to_run = ["bash", "./update_cache.sh", CACHE_PATH, url]
    if reference:
        cmd_to_run.append(reference)
    results = subprocess.run(
        cmd_to_run, stdout=subprocess.PIPE).stdout.decode()

    for line in results.split('\n'):
        if line.startswith("INFO: "):
            LOGGER.info(line.replace("INFO: ", ""))
        if line.startswith("DEBUG: "):
            LOGGER.debug(line.replace("DEBUG: ", ""))
        if line.startswith("ERROR: "):
            LOGGER.error(line.replace("ERROR: ", ""))
        if line.startswith("WARN: "):
            LOGGER.warning(line.replace("WARN: ", ""))

    # Consistency check
    try:
        check_op_validity(repository_path, url)
    except Exception:
        return

# Remove previous update result
try:
    os.remove("%s/fetch.yml" % CACHE_PATH)
except:
    # If first run, nothing to remove
    pass

# Fetch repositories
with Pool(SIMULTANEOUS_CONNECTIONS) as p:
    p.map(fetch_repo, REPO_LIST)

# Update active operators folder
ignored_patterns = [
    ".git",
    "test",
    "test/",
    "tests",
    "tests/",
    "test_*.py",
    "tests_*.py"
]
ignored = shutil.ignore_patterns(*ignored_patterns)
results = []
# Empty active operators before adding requested ones
shutil.rmtree("%s/" % (OP_PATH), ignore_errors=True)
# Add requested operators to active list
for repo in get_yaml_content("%s/fetch.yml" % CACHE_PATH):
    repository_path = "%s/%s" % (CACHE_PATH, repo.get("cache"))
    url = repo.get("url")
    op_name = extract_repo_name(url)

    if os.path.exists("%s/%s" % (OP_PATH, op_name)):
        LOGGER.error("Operator already exist with the same name %s", op_name)
    else:
        shutil.copytree("%s/%s" % (repository_path, op_name),
                    "%s/%s" % (OP_PATH, op_name), ignore=ignored)
    if os.path.exists("%s/LICENSE" % (repository_path)):
        shutil.copy("%s/LICENSE" % (repository_path),
                    "%s/%s/" % (OP_PATH, op_name))
    if os.path.exists("%s/README.md" % (repository_path)):
        shutil.copy("%s/README.md" % (repository_path),
                    "%s/%s/" % (OP_PATH, op_name))
    for catalog_def_file in glob.glob("%s/*.json" % (repository_path)):
        shutil.copy(catalog_def_file, "%s/%s/" % (OP_PATH, op_name))

    # Prepare versions manifest
    del(repo["cache"])
    results.append(repo)


# Create Operators Version manifest
with open("%s/versions.yml" % OP_PATH, 'w') as output_stream:
    yaml.dump(results, output_stream, default_flow_style=False)


# Processing catalog for operators
catalog.delete_catalog_postgres()
catalog.populate_catalog_families()
for repo in results:
    catalog.process_operator_catalog(extract_repo_name(repo.get("url")))


def show_summary():
    """
    Display summary as debug
    """
    with open("%s/versions.yml" % OP_PATH, 'r') as f:
        for line in f:
            LOGGER.debug(line.rstrip('\n'))


show_summary()
