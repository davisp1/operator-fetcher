# operator-fetcher

This project aims at preparing operators to send to an IKATS instance.

This operation consists in several parts :

- Based on a repository list, fetch the operators to be used
- Check the integrity of each operator
- Build the operators tree
- Update catalog in database
- Make this tree available to other services

## Quickstart

To build the image

```bash
docker build . -t operator-fetcher
```

To run the container

```bash
docker run -it \
   -e DB_HOST=${database_host} \
   -e DB_PORT=${database_port} \
   -e DB_USER=${database_username} \
   -e DB_PWD=${database_password} \
   -e CONNECTION_TIMEOUT=5 \
   -v /path/to/cached/operators:/app/fetch-op \
   -v /path/to/shared/operators:/app/op \
   -v /path/to/local/operators:/app/local \
   -v /path/to/custom/repo-list.yml:/app/repo-list.yml \
   operator-fetcher
```

`CONNECTION_TIMEOUT` corresponds to the number of seconds the app will wait until considering the repository not reachable.
Default value is 5. Increase the value if you have a bad connection.

## Content of repo-list.yml

`repo-list.yml` is the file that indicates where to fetch the operators.

It is a [YAML](http://yaml.org/) file describing a list of the following information:

1.  **url**: the complete URL to the `git` repository.  
    This may be a:

    - complete https URL (eg. `https://github.com/IKATS/op-quality_stats.git`)
    - local path (see details below)

    If credentials must be provided, use the following format: `https://login:password@company.com/git_repo`

2.  **ref**: a `git`reference to the commit to use  
    This may be a:
    - sha1: (eg. `04c113bc093dc748583690474d81470b39e05cc8`)
    - branch: (eg. `master`)
    - tag: (eg. `1.8.2`)
    - relative reference: (eg. `master^`)

## Volumes

4 volumes are used :

- `/app/fetch-op`: (_optional_) the path to the fetched operators to be prepared. Mounting it allows faster startup (act as a _cache_)
- `/app/op`: (_mandatory_) the path to the prepared operators to be provided to other services
- `/app/repo-list.yml` : (_optional_) to set an external repository list different from the official IKATS operators
- `/app/local`: (_optional_) if you plan to use local operator, mount your git workspace here.

## Mounting a local operator repository

**Assumption:**  
The repository is located on host machine at `/home/developer/op-mysterious-operator`

- Mount `/home/developer/op-mysterious-operator` to `/app/local/op-mysterious-operator`
- In `repo-list.yml` file, set the `url` field to `/app/local/op-mysterious-operator`

## Cache

Operators are fetched into a local cache mounted at `/app/fetch-op`.
This cache is never cleaned to not rely on Internet connection.

## Workflow

- Clean the _applicable operators path_ content
- For each operator listed in `repo-list.yml`, do as follows:
  - If operator is not present in cache
    - Try to get it from the `url`
    - If not reachable (not connected to network, wrong credentials, URL mispelled), skip the operator
  - If operator is present in cache
    - Try to get the latest sources
    - Switch to the desired reference
    - If the desired reference is not found (or latest version not available) , keep the current reference
  - Copy and format operator to the _applicable operators path_
- Generate a manifest indicating the activated operators containing (for each operator):
  - `url` : url described in `repo-list.yml`
  - `old_commit` : corresponds to the commit sha1 of the previous run
  - `commit` : corresponds to the commit sha1 of the current run
  - `ref` : corresponds to the requested reference of the current run

## Messages

> [%s] No catalog file found.

This message appears when there is no catalog definition file in folder or if it doesn't match the regexp pattern : `catalog_def(_[0-9]{,2})?.json`.
This warning means that the operator won't be available in IKATS.

> Operator already exist with the same name %s

This occurs when at least 2 operators having the same root name are present in `repo-list.yml`.
You must rename them or activate only one of them.

> reference %s not found in repo %s

This occurs when there is no connection to the url (not connected to network, wrong credentials, URL mispelled).
The fetch can't be performed so the new reference is not available.
You need a connection to the sources.

> %s can't be cloned

This occurs when there is no connection to the url (not connected to network, wrong credentials, URL mispelled) and no cache is present.
You need a connection to the sources.

> JSON bad format for %s

The catalog_def.json contains errors
In this case, the operator is ignored
