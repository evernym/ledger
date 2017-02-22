#!groovy​

try {

// ALL BRANCHES: master, stable, PRs

    // 1. TEST
    stage('Test') {
        parallel 'ubuntu-test':{
            node('ubuntu') {
                stage('Ubuntu Test') {
                    testUbuntu()
                }
            }
        },
        'windows-test':{
            node('windows') {
                stage('Windows Test') {
                    testWindows()
                }
            }
        }
    }

// MASTER AND STABLE ONLY

    if (env.BRANCH_NAME != 'master' && env.BRANCH_NAME != 'stable') {
        echo "Ledger ${env.BRANCH_NAME}: skip publishing"
        return
    }

    // 2. PUBLISH TO PYPI
    stage('Publish to pypi') {
        node('ubuntu') {
            version = publishToPypi()
        }
    }

    // 3. BUILD PACKAGES
    stage('Build packages') {
        parallel 'ubuntu-build':{
            node('ubuntu') {
                stage('Build deb packages') {
                    buildDeb()
                }
            }
        },
        'windows-build':{
            stage('Build msi packages') {
                buildMsi()
            }
        }
    }

    // 4. SYSTEM TESTS
    stage('System tests') {
        systemTests()
    }

// MASTER ONLY

    if (env.BRANCH_NAME != 'stable') {
        return
    }

    // 5. NOTIFY QA
    stage('QA notification') {
        notifyQA(version)
    }

    // 6. APPROVE QA
    def qaApproval
    stage('QA approval') {
        qaApproval = approveQA()
    }
    if (!qaApproval) {
        return
    }

    // 6. RELEASE PACKAGES
    stage('Release packages') {
        echo 'TODO: Implement me'
    }

    // 7. SYSTEM TESTS FOR RELEASE
    stage('System tests') {
        echo 'TODO: Implement me'
    }

} catch(e) {
    currentBuild.result = "FAILED"
    notifyFailed()
    throw e
}

def testUbuntu() {
    try {
        echo 'Ubuntu Test: Checkout csm'
        checkout scm


        echo 'Ubuntu Test: Build docker image'
        sh 'ln -sf ci/ledger-ubuntu.dockerfile Dockerfile'
        def testEnv = docker.build 'ledger-test'

        testEnv.inside {
            echo 'Ubuntu Test: Install dependencies'
            sh 'cd /home/sovrin && virtualenv -p python3.5 test'
            sh '/home/sovrin/test/bin/python setup.py install'
            sh '/home/sovrin/test/bin/pip install pytest'

            echo 'Ubuntu Test: Test'
            try {
                sh '/home/sovrin/test/bin/python -m pytest --junitxml=test-result.xml'
            }
            finally {
                junit 'test-result.xml'
            }
        }
    }
    finally {
        echo 'Ubuntu Test: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def testWindows() {
    try {
        echo 'Windows Test: Checkout csm'
        checkout scm


        echo 'Windows Test: Build docker image'
        sh 'cp "ci/ledger-windows.dockerfile" Dockerfile'
        sh 'docker build -t "ledger-windows-test" .'
        sh 'bash -c "if [ -n \"$(docker ps -a | grep borng_euclid)\" ]; then docker rm --force test-container; fi"'
        sh 'chmod -R a+w $PWD'
        sh 'docker run -id --name test-container -v "$(cygpath -w $PWD):C:\\test" "ledger-windows-test"'
        sh 'docker exec -i test-container cmd /c "cd \"C:\\test\" && dir"'
        sh 'docker exec -i test-container cmd /c "cd \"C:\\test\" && python setup.py install"'
        sh 'docker exec -i test-container cmd /c "pip install pytest"'
        sh 'docker exec -i test-container cmd /c "cd \"C:\\test\" && pytest --junitxml=test-result.xml"'
        sh 'docker stop test-container'
        sh 'docker rm test-container'
        junit 'test-result.xml'
    }
    finally {
        echo 'Ubuntu Test: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def publishToPypi() {
    try {
        echo 'Publish to pypi: Checkout csm'
        checkout scm

        echo 'Publish to pypi: Prepare package'
        sh 'chmod -R 777 ci'
        //gitCommit = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
        version = sh(returnStdout: true, script: 'ci/get-package-version.sh ledger $BUILD_NUMBER').trim()

        sh 'ci/prepare-package.sh . $BUILD_NUMBER'

        echo 'Publish to pypi: Publish'
        withCredentials([file(credentialsId: 'pypi_credentials', variable: 'FILE')]) {
            sh 'ln -sf $FILE $HOME/.pypirc'
            sh 'ci/upload-pypi-package.sh .'
            sh 'rm -f $HOME/.pypirc'
        }

        return version
    }
    finally {
        echo 'Publish to pypi: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def buildDeb() {
    try {
        echo 'Build deb packages: Checkout csm'
        checkout scm

        echo 'Build deb packages: Prepare package'
        sh 'chmod -R 777 ci'
        sh 'ci/prepare-package.sh . $BUILD_NUMBER'

        echo 'Build deb packages: Build debs'
        withCredentials([usernameColonPassword(credentialsId: 'evernym-githib-user', variable: 'USERPASS')]) {
            sh 'git clone https://$USERPASS@github.com/evernym/sovrin-packaging.git'
        }
        echo 'TODO: Implement me'
        // sh ./sovrin-packaging/pack-ledger.sh $BUILD_NUMBER


        echo 'Build deb packages: Publish debs'
        echo 'TODO: Implement me'
        // sh ./sovrin-packaging/upload-build.sh $BUILD_NUMBER
    }
    finally {
        echo 'Build deb packages: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def buildMsi() {
    echo 'TODO: Implement me'
}

def systemTests() {
    echo 'TODO: Implement me'
}

def notifyQA(version) {
    emailext (
        subject: "New release candidate 'ledger-$version' is waiting for approval",
        body: "Please go to ${BUILD_URL} and verify the build",
        to: 'alexander.sherbakov@dsr-company.com'
    )
}

def approveQA() {
    def qaApproval
    try {
        input(message: 'Do you want to publish this package?')
        qaApproval = true
        echo 'QA approval granted'
    }
    catch (Exception err) {
        qaApproval = false
        echo 'QA approval denied'
    }
    return qaApproval
}


def notifyFailed() {
    emailext (
        body: '$DEFAULT_CONTENT',
        recipientProviders: [
            [$class: 'CulpritsRecipientProvider'],
            [$class: 'DevelopersRecipientProvider'],
            [$class: 'RequesterRecipientProvider']
        ],
        replyTo: '$DEFAULT_REPLYTO',
        subject: '$DEFAULT_SUBJECT',
        to: '$DEFAULT_RECIPIENTS'
       )
}
