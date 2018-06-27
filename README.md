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
   -v /path/to/cached/operators:/app/fetch-op \
   -v /path/to/shared/operators:/app/op \
   -v /path/to/local/operators:/app/local \
   -v /path/to/custom/repo-list.yml:/app/repo-list.yml \
   operator-fetcher
```

## Content of repo-list.yml

`repo-list.yml` is the file that indicates where to fetch the operators.

It is a [YAML](http://yaml.org/) file describing a list of the following information:

1. **url**: the complete URL to the `git` repository.  
   This may be a:
   - complete https URL (eg. `https://github.com/IKATS/op-quality_stats.git`)
   - local path (see details below)

   If credentials must be provided, use the following format: `https://login:password@company.com/git_repo`
2. **ref**: a `git`reference to the commit to use  
   This may be a:
   - sha1:  (eg. `04c113bc093dc748583690474d81470b39e05cc8`)
   - branch:  (eg. `master`)
   - tag:  (eg. `1.8.2`)
   - relative reference:  (eg. `master^`)

## Volumes

4 volumes are used :

- `/app/fetch-op`: (*optional*) the path to the fetched operators to be prepared. Mounting it allows faster startup (act as a *cache*)
- `/app/op`: (*mandatory*) the path to the  prepared operators to be provided to other services
- `/app/repo-list.yml` : (*optional*) to set an external repository list different from the official IKATS operators
- `/app/local`: (*optional*) if you plan to use local operator, mount your git workspace here.

## Mounting a local operator repository

**Assumption:**  
The repository is located on host machine at `/home/developer/op-mysterious-operator`

- Mount `/home/developer/op-mysterious-operator` to `/app/local/op-mysterious-operator`
- In `repo-list.yml` file, set the `url` field to `/app/local/op-mysterious-operator`

## Common errors

### No catalog

```text
WARNING:No catalog file found for [op-xxxxx] (url: https://xxxxx )
```

This message appears when there is no catalog definition file in folder or if it doesn't match the regexp pattern : `catalog_def(_[0-9]{,2})?.json`.

This warning means that the operator won't be available in IKATS. 

### Can't clone

```text
Impossible to clone https://xxxxx
```

It may happens in the following cases:

- Not connected to Network
- Wrong credentials
- URL is misspelled

in this case, the operator is skipped

### JSON bad format for op-xxxxx

```text
JSON bad format for op-xxxx/xxxxxx.json
```

The catalog_def.json contains errors
In this case, the operator is ignored