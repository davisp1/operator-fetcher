#!/bin/bash

# Check if the repo pointed by url is already in local cache
# echo the repo folder name if found, nothing otherwise

repoCache=$1
url=$2

for repo in $(ls ${repoCache} | grep -v versions.yml)
do
  pushd ${repoCache}/$repo > /dev/null
  repoUrl=$(git remote get-url origin)
  test "${repoUrl}" == "${url}" && echo ${repo} && exit 0
  popd > /dev/null
done
exit 1