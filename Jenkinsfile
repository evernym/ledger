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
            def testEnv = docker.build 'ledger-test'
            echo 'Build docker image: done'
            testEnv.inside {
                echo 'Install deps...'
                sh 'sudo python3 setup.py install'
                sh 'sudo pip3 install pytest'
                echo 'Install deps: done'

                echo 'Testing...'
                sh 'python3 -m pytest --junitxml=./test-result'
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
    node('deploy') {
        stage('Checkout csm') {
            echo 'Checkout csm...'
            checkout scm
            echo 'Checkout csm: done'
        }
        
        stage('Publish pipy') {
            echo 'Publish to pipy...'
            sh ./ci/prepare-pypi-package.sh . $BUILD_NUMBER
            sh ./ci/upload-pypi-package.sh .
            echo 'Publish pipy: done'
        }

        stage('Building debs') {
            echo 'Building debs...'
            git clone 'https://github.com/evernym/sovrin-packaging.git'
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
