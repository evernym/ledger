#!groovy​

@Library('SovrinHelpers') _

def name = 'ledger'

def testUbuntu = {
    try {
        echo 'Ubuntu Test: Checkout csm'
        checkout scm

        echo 'Ubuntu Test: Build docker image'
        def testEnv = dockerHelpers.build(name)

        testEnv.inside {
            echo 'Ubuntu Test: Install dependencies'
            testHelpers.installDeps()

            echo 'Ubuntu Test: Test'
            testHelpers.testJunit()
        }
    }
    finally {
        echo 'Ubuntu Test: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def testWindows = {
    try {
        echo 'Windows Test: Checkout csm'
        checkout scm

        echo 'Windows Test: Build docker image'
        dockerHelpers.execWindows(name, testHelpers.installDepsWindowsCommands() + testHelpers.testJunitWindowsCommands())
        junit 'test-result.xml'
    }
    finally {
        echo 'Windows Test: Cleanup'
        step([$class: 'WsCleanup'])
    }
}

def testWindowsNoDocker = {
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

testAndPublish(name, [ubuntu: testUbuntu])