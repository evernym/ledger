#!groovy​

stage('Test') {
    parallel 'ubuntu-test':{
        node('ubuntu') {
            try {
                stage('Ubuntu Test: Checkout csm') {
                    checkout scm
                }

                stage('Ubuntu Test: Build docker image') {
                    sh 'ln -sf ci/ledger-ubuntu.dockerfile Dockerfile'
                    def testEnv = docker.build 'ledger-test'

                    testEnv.inside {
                        stage('Ubuntu Test: Install dependencies') {
                            sh 'cd /home/sovrin && virtualenv -p python3.5 test'
                            sh '/home/sovrin/test/bin/python setup.py install'
                            sh '/home/sovrin/test/bin/pip install pytest'
                        }

                        stage('Ubuntu Test: Test') {
                            try {
                                sh '/home/sovrin/test/bin/python -m pytest --junitxml=test-result.xml'
                            }
                            finally {
                                junit 'test-result.xml'
                            }
                        }
                    }
                }
            }
            finally {
                stage('Ubuntu Test: Cleanup') {
                    step([$class: 'WsCleanup'])
                }
            }
        }
    },
    'windows-test':{
        echo 'TODO: Implement me'
    }
}

if (env.BRANCH_NAME != 'master' && env.BRANCH_NAME != 'stable') {
    echo "Ledger ${env.BRANCH_NAME}: skip publishing"
    return
}



stage('Publish to pypi') {
    node('ubuntu') {
        try {
            stage('Publish to pypi: Checkout csm') {
                checkout scm
            }

            stage('Publish to pypi: Prepare package') {
                sh 'chmod -R 777 ci'
                sh 'ci/prepare-package.sh . $BUILD_NUMBER'
            }

            stage('Publish to pypi: Publish') {
                sh 'chmod -R 777 ci'
                withCredentials([file(credentialsId: 'pypi_credentials', variable: 'FILE')]) {
                    sh 'ln -sf $FILE $HOME/.pypirc'
                    sh 'ci/upload-pypi-package.sh .'
                    sh 'rm -f $HOME/.pypirc'
                }
            }
        }
        finally {
            stage('Publish to pypi: Cleanup') {
                step([$class: 'WsCleanup'])
            }
        }
    }
}

stage('Build and publish') {
    parallel 'ubuntu-build':{
        node('ubuntu') {
            try {
                stage('Build and publish: Checkout csm') {
                    checkout scm
                }

                stage('Build and publish: Prepare package') {
                    sh 'chmod -R 777 ci'
                    sh 'ci/prepare-package.sh . $BUILD_NUMBER'
                }

                stage('Build and publish: Build debs') {
                    withCredentials([usernameColonPassword(credentialsId: 'evernym-githib-user', variable: 'USERPASS')]) {
                        sh 'git clone https://$USERPASS@github.com/evernym/sovrin-packaging.git'
                    }
                    echo 'TODO: Implement me'
                    // sh ./sovrin-packaging/pack-ledger.sh $BUILD_NUMBER
                }

                stage('Build and publish: Publish debs') {
                    echo 'TODO: Implement me'
                    // sh ./sovrin-packaging/upload-build.sh $BUILD_NUMBER
                }
            }
            finally {
                stage('Build and publish: Cleanup') {
                    step([$class: 'WsCleanup'])
                }
            }
        }
    },
    'windows-build':{
        echo 'TODO: Implement me'
    }
}

stage('System tests') {
    echo 'TODO: Implement me'
}

if (env.BRANCH_NAME == 'stable') {

    stage('QA notification') {
        emailext (
            subject: "New release candidate for $PROJECT_NAME: [$BUILD_NUMBER]'",
            body: "See ${env.BUILD_URL}"
            to: 'alexander.sherbakov@dsr-company.com'
        )
    }

    def qaApproval
    stage('QA approval') {
        try {
            input(message: 'Do you want to publish this package?')
            qaApproval = true
            echo 'QA approval granted'
        }
        catch (Exception err) {
            qaApproval = false
            echo 'QA approval denied'
        }
    }
    if (!qaApproval) {
        return
    }

    stage('Release packages') {
        echo 'TODO: Implement me'
    }

    stage('System tests') {
        echo 'TODO: Implement me'
    }

}

