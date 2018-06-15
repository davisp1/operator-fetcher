pipeline {
    agent any

    stages {
        stage('Fetch SCM') {
            steps {
                checkout scm
            }
        }

        stage('Build the image') {
            agent { node { label 'docker' } }

            steps {
                script {
                    opFetcher = docker.build("operator-fetcher", "--pull .")

                    fullBranchName = "${env.BRANCH_NAME}"
                    branchName = fullBranchName.substring(fullBranchName.lastIndexOf("/") + 1)
                    shortCommit = "${GIT_COMMIT}".substring(0, 7)

                    docker.withRegistry("${env.REGISTRY_ADDRESS}", 'DOCKER_REGISTRY') {
                        /* Push the container to the custom Registry */
                        opFetcher.push(branchName + "_" + shortCommit)
                        opFetcher.push(branchName + "_latest")
                          if (branchName == "master") {
                            opFetcher.push("master")
                            opFetcher.push("latest")
                          }
                    }
                }
            }
        }
    }
}
