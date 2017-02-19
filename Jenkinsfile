#!groovy​

echo 'Ledger test...'

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
                        sh 'virtualenv -p python3.5 test'
                        sh 'test/bin/python setup.py install'
                        sh 'test/bin/pip install pytest'
                    }

                    stage('Ubuntu Test: Test') {
                        try {
                            sh 'cd ledger && ../test/bin/python -m pytest --junitxml=../test-result.xml'
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

echo 'Ledger test: done'

def qaApproval
stage('QA approval') {
	try {
		qaApproval = input(message: 'Do you want to publish this package?')
		echo 'QA approval granted'
	}
	catch (Exception err) {
		echo 'QA approval denied'
	}
}
echo "${qaApproval}"

if (env.BRANCH_NAME != 'master' && env.BRANCH_NAME != 'stable') {
    echo "Ledger ${env.BRANCH_NAME}: skip publishing"
    return
}

echo 'Ledger build...'

node('ubuntu') {
    try {
        stage('Publish: Checkout csm') {
            checkout scm
        }

        stage('Publish: Prepare package') {
        	sh 'chmod -R 777 ci'
        	sh 'ci/prepare-package.sh . $BUILD_NUMBER'
        }
        
        stage('Publish: Publish pipy') {
            sh 'chmod -R 777 ci'
            withCredentials([file(credentialsId: 'pypi_credentials', variable: 'FILE')]) {
                sh 'ln -sf $FILE $HOME/.pypirc' 
                sh 'ci/upload-pypi-package.sh .'
                sh 'rm -f $HOME/.pypirc'
            }
        }

        stage('Publish: Build debs') {
            withCredentials([usernameColonPassword(credentialsId: 'evernym-githib-user', variable: 'USERPASS')]) {
                sh 'git clone https://$USERPASS@github.com/evernym/sovrin-packaging.git'
            }
            echo 'TODO: Implement me'
            // sh ./sovrin-packaging/pack-ledger.sh $BUILD_NUMBER
        }

        stage('Publish: Publish debs') {
            echo 'TODO: Implement me'
            // sh ./sovrin-packaging/upload-build.sh $BUILD_NUMBER
        }
    }
    finally {
        stage('Publish: Cleanup') {
            step([$class: 'WsCleanup'])
        }
    }
}

echo 'Ledger build: done'