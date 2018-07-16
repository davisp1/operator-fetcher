#!/bin/bash

url=$1
reference=$2

USAGE(){
cat <<EOF

USAGE

  update_cache.sh <url> <reference>

  url:       path to git repository to use
  reference: commit/branch/tag/relative reference to git commit to use

EOF
}

if [[ $# -ne 2 ]]
then
  USAGE
  exit 1
fi

repoCache=/app/fetch-op
# TODO fix before commit
repoCache=/tmp/fetch-op

# Go to cache folder
cd ${repoCache}

# check if connected or not (url is reachable)
connectedStatus=0
timeout 2 git ls-remote ${url} > /dev/null 2>&1
test $? -eq 0 && connectedStatus=1 || connectedStatus=0

versions_file=${repoCache}/versions.yml
writeStatus(){
cat >> ${versions_file} <<EOL
- url: ${1}
  ref: ${2}
  commit: ${3}
  cache: ${4}
EOL
}

cloneNew(){
  repoFolder=$(mktemp -d ${repoCache}/op-XXXXX)
  pushd $repoFolder > /dev/null
  git clone -b ${reference} ${url} .
  popd > /dev/null
  cd ${repoFolder}
  writeStatus "$url" "$reference" $(git rev-parse --short HEAD) $(basename ${repoFolder})
}

# Check if the repo pointed by url is already in local cache
# echo the repo folder name if found, nothing otherwise
getMatchingCacheRepo(){
  for repo in $(ls ${repoCache} | grep -v versions.yml)
  do
    pushd ${repoCache}/$repo > /dev/null
    repoUrl=$(git remote get-url origin)
    test "${repoUrl}" == "${url}" && echo ${repo} && return
    popd > /dev/null
  done
}

repoFolder=$(getMatchingCacheRepo)
test -z "$repoFolder" && newRepo=1 || newRepo=0

# Detect use case
repoName=$(getMatchingCacheRepo)
if test -z "${repoName}";then
  # Repository not in cache
  if test ${connectedStatus} -eq 1;then
    # Trying to clone
    cloneNew
    exit 0
  else
    echo "${url} can't be cloned"
    exit 2
  fi
else
  # Repository exists in cache
  cd ${repoName}
  test ${connectedStatus} -eq 1 && git fetch --all --prune --tags --recurse-submodules --jobs=4
  git checkout ${reference}
  writeStatus "$url" "$reference" $(git rev-parse --short HEAD) $(basename ${repoFolder})
fi
