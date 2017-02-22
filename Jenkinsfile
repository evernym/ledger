#!groovy​

def success = true
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
            node('windows2016') {
                stage('Windows Test') {
                    testWindows()
                }
            }
        },
        'windows-no-docker-test':{
            node('windows2012') {
                stage('Windows No Docker Test') {
                    testWindowsNoDocker()
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
        parallel 'ubuntu-system-tests':{
            stage('Ubuntu system tests') {
                ubuntuSystemTests()
            }
        },
        'windows-system-tests':{
            stage('Windows system tests') {
                windowsSystemTests()
            }
        }
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

    // 7. RELEASE PACKAGES
    stage('Release packages') {
        parallel 'ubuntu-release-packages':{
            stage('Ubuntu release packages') {
                echo 'TODO: Implement me'
            }
        },
        'windows-release-packages':{
            stage('Windows release packages') {
                echo 'TODO: Implement me'
            }
        }
    }

    // 8. SYSTEM TESTS FOR RELEASE
    stage('Release system tests') {
        parallel 'ubuntu-system-tests':{
            stage('Ubuntu system tests') {
                ubuntuSystemTests()
            }
        },
        'windows-system-tests':{
            stage('Windows system tests') {
                windowsSystemTests()
            }
        }
    }

} catch(e) {
    success = false
    currentBuild.result = "FAILED"
    notifyFailed()
    throw e
} finally {
    if (success) {
        currentBuild.result = "SUCCESS"
        notifySuccess()
    }
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
        sh 'docker rm --force ledger_test_container || true'
        sh 'chmod -R a+w $PWD'
        sh 'docker run -id --name ledger_test_container -v "$(cygpath -w $PWD):C:\\test" "ledger-windows-test"'
        // XXX robocopy will return 1, and this is OK and means success (One of more files were copied successfully),
        // that's why " || true"
        sh 'docker exec -i ledger_test_container cmd /c "robocopy C:\\test C:\\test2 /COPYALL /E" || true'
        sh 'docker exec -i ledger_test_container cmd /c "cd C:\\test2 && python setup.py install"'
        sh 'docker exec -i ledger_test_container cmd /c "cd C:\\test2 && pytest --junit-xml=C:\\test\\test-result.xml"'
        sh 'docker stop ledger_test_container'
        sh 'docker rm ledger_test_container'
        junit 'test-result.xml'
    }
    finally {
        echo 'Ubuntu Test: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def testWindowsNoDocker() {
    def virtualEnvDir = "$USERPROFILE\\$BRANCH_NAME$BUILD_NUMBER"
    try {
        echo 'Windows No Docker Test: Checkout csm'
        checkout scm

        echo 'Windows No Docker Test: Install dependencies'
        bat "if exist $virtualEnvDir rmdir /q /s $virtualEnvDir"
        bat "virtualenv $virtualEnvDir"
        bat "$virtualEnvDir\\Scripts\\python setup.py install"
        bat "$virtualEnvDir\\Scripts\\pip install pytest"
        
        echo 'Windows No Docker Test: Test'
        try {
            bat "$virtualEnvDir\\Scripts\\python -m pytest --junitxml=test-result.xml"
        }
        finally {
            junit 'test-result.xml'
        }
    }
    finally {
        echo 'Windows No Docker Test: Cleanup'
        bat "if exist $virtualEnvDir rmdir /q /s $virtualEnvDir"
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

        dir('sovrin-packaging') {
            echo 'Build deb packages: get packaging code'
            git branch: 'jenkins-poc', credentialsId: 'evernym-githib-user', url: 'https://github.com/evernym/sovrin-packaging'

            echo 'Build deb packages: Build debs'
            def sourcePath = sh(returnStdout: true, script: 'readlink -f ..').trim()
            sh "./pack-debs $BUILD_NUMBER ledger $sourcePath"

            echo 'Build deb packages: Publish debs'
            def repo = env.BRANCH_NAME == 'stable' ? 'rc' : 'master'
            //sh "./upload-debs $BUILD_NUMBER ledger $repo"
        }
    }
    finally {
        echo 'Build deb packages: Cleanup'
        dir('sovrin-packaging') {
            deleteDir()
        }
        step([$class: 'WsCleanup'])
    }
}

def buildMsi() {
    echo 'TODO: Implement me'
}

def ubuntuSystemTests() {
    echo 'TODO: Implement me'
}

def windowsSystemTests() {
    echo 'TODO: Implement me'
}

def notifyQA(version) {
    emailext (
        subject: "New release candidate 'ledger-$version' is waiting for approval",
        body: "Please go to ${BUILD_URL}console and verify the build",
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

def notifySuccess() {
    emailext (
        body: '$DEFAULT_CONTENT',
        recipientProviders: [
            [$class: 'CulpritsRecipientProvider'],
            [$class: 'DevelopersRecipientProvider'],
            [$class: 'RequesterRecipientProvider']
        ],
        replyTo: '$DEFAULT_REPLYTO',
        subject: "New ${BRANCH_NAME} build 'ledger-$version'",
        to: '$DEFAULT_RECIPIENTS'
       )
}