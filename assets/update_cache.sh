#!/bin/bash

repoCache=$1
url=$2
reference=$3

CONNECTION_TIMEOUT=10

USAGE(){
  cat <<EOF
USAGE

  update_cache.sh <repoCache> <url> <reference>

  repoCache: Cache folder where operatorss are fetched
  url:       path to git repository to use
  reference: commit/branch/tag/relative reference to git commit to use

EOF
}

if [[ $# -gt 3 ]]
then
    USAGE
    exit 1
fi

# Try to get the remote
repoFolder=$(bash getMatchingCacheRepo.sh ${repoCache} ${url})
test -z "$repoFolder" && newRepo=1 || newRepo=0

# Go to cache folder
cd ${repoCache}

# check if connected or not (url is reachable)
connectedStatus=0
timeout ${CONNECTION_TIMEOUT} git ls-remote ${url} > /dev/null 2>&1
test $? -eq 0 && connectedStatus=1 || connectedStatus=0

versions_file=${repoCache}/fetch.yml

# Display a status on screen and in versions.yml file
writeStatus(){
    oldCommit=$1
    commit=$2
    folder=$3
    
cat >> ${versions_file} <<EOL
- url: ${url}
  ref: ${reference:-HEAD}
  commit: ${commit}
  old_commit: ${oldCommit}
  cache: ${folder}
EOL
    
    changeTxt="$oldCommit -> $commit"
    if test "$oldCommit" == "$commit"; then
        changeTxt="Keep $commit"
    else
        if test -z "$oldCommit"; then
            changeTxt="New $commit"
        else
            changeTxt="Update $oldCommit to $commit"
        fi
    fi
    printf "INFO: [%s] Requested:%s|%s|folder:%s\n" "$url" "${reference:-HEAD}" "$changeTxt" "$folder"
}

# Get the commit sha1 from a specified git repo path and suffix by "_modified" if locally modified
getCommitStatus(){
    commit=$(git rev-parse --short HEAD)
    test $(git status --porcelain|wc -l) -gt 1 && commit="${commit}_modified"
    echo $commit
}

# Clone the repository in the cache
cloneNew(){
    fullRepoPath=$(mktemp -d ${repoCache}/op-XXXXX)
    pushd $fullRepoPath > /dev/null
    if [[ $url != http://* && $url != https://* && $url != git://* ]]; then
        # URL doesn't begin with http|https|git ://, indicating it is a local folder
        # Using this way, relative path are also handled
        # Sync folders since there is no simple way to detect a change
        rsync -ah $(realpath ${url})/. ${fullRepoPath} --delete
        # Adding remote for next lookup (with absolute path)
        git remote remove origin 2> /dev/null
        git remote add origin $(realpath ${url})
    else
        git clone -qb ${reference:-master} ${url} .
    fi
    commit=$( getCommitStatus )
    popd > /dev/null
    writeStatus "" "$commit" $(basename ${fullRepoPath})
}

# Update the repo to the requested reference if available.
# Keep old one if any error occurs
updateToRef(){
    pushd ${repoCache}/${repoFolder} > /dev/null
    oldCommit=$(getCommitStatus)
    
    if [[ $url != http://* && $url != https://* && $url != git://* ]]; then
        # URL doesn't begin with http|https|git ://, indicating it is a local folder
        rsync -ah $(realpath ${url})/. ${repoCache}/${repoFolder} --delete
        # Adding remote for next lookup (with absolute path)
        git remote remove origin 2> /dev/null
        git remote add origin $(realpath ${url})
    else
        # This is a remote repository, try to fetch latest commits to be able to switch to it
        test ${connectedStatus} -eq 1 && git fetch -q --all --prune --tags
        git checkout -q ${reference} 2> /dev/null || echo "ERROR: reference $reference not found in repo $url"
    fi
    
    commit=$(getCommitStatus)
    popd > /dev/null
    writeStatus "${oldCommit}" "${commit}" "${repoFolder}"
}

# Detect use case
if test -z "${repoFolder}";then
    # Repository not in cache
    if test ${connectedStatus} -eq 1;then
        # Trying to clone
        cloneNew
        exit 0
    else
        echo "ERROR: ${url} can't be cloned"
        exit 2
    fi
else
    # Repository exists in cache
    updateToRef
    exit 0
fi
