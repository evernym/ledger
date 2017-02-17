echo 'Ledger build...'

stage('Ubuntu testing') {
    node('ubuntu') {
        stage('Checkout csm') {
            echo 'Checkout csm...'
            checkout scm
            echo 'Checkout csm: done'
        }

        stage('Install dependencies and test...') {
            echo 'Build docker image...'
            sh 'cp ci/ledger-ubuntu.dockerfile Dock'
            def testEnv = docker.build 'ledger-test'
            echo 'Build docker image: done'
            testEnv.inside {
                echo 'Creating to virtual environment...'
                sh 'virtualenv -p python3.5 test'
                echo 'Creating to virtual environment: done'

                echo 'Install deps...'
                sh 'test/bin/python setup.py install'
                echo 'Install deps: done'

                echo 'Install pytest...'
                sh 'test/bin/pip install pytest'
                echo 'Install pytest: done'

                echo 'Testing...'
                sh 'cd ledger && ../test/bin/python -m pytest --junitxml=./test-result'
                echo 'Testing: done'
            }
        }

        stage('Cleanup') {
            echo 'Cleanup workspace...'
            step([$class: 'WsCleanup'])
            echo 'Cleanup workspace: done'
        }
    }
}

stage('Publish artifacts') {
    node('ubuntu') {
        stage('Checkout csm') {
            echo 'Checkout csm...'
            checkout scm
            echo 'Checkout csm: done'
        }
        
        stage('Publish pipy') {
            echo 'Publish to pipy...'
            sh 'chmod -R 777 ci'
            withCredentials([file(credentialsId: 'pypi_credentials', variable: 'FILE')]) {
                sh 'ln -s $FILE $HOME/.pypirc' 
                sh 'ci/prepare-pypi-package.sh . $BUILD_NUMBER'
                sh 'ci/upload-pypi-package.sh .'
                sh 'rm $HOME/.pypirc'
            }
            echo 'Publish pipy: done'
        }

        stage('Building debs') {
            echo 'Building debs...'
            sh 'git clone https://github.com/evernym/sovrin-packaging.git'
            // sh ./sovrin-packaging/pack-ledger.sh $BUILD_NUMBER
            echo 'Building debs: done'
        }

        stage('Publishing debs') {
            echo 'Publish debs...'
            // sh ./sovrin-packaging/upload-build.sh $BUILD_NUMBER
            echo 'Publish debs: done'
        }

        stage('Cleanup') {
            echo 'Cleanup workspace...'
            step([$class: 'WsCleanup'])
            echo 'Cleanup workspace: done'
        }
    }
}

echo 'Ledger build: done'
