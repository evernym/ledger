FROM microsoft/windowsservercore

LABEL Description="ledger" Vendor="Evernym"

# Install environment

#   Python
RUN powershell.exe -Command \
    $ErrorActionPreference = 'Stop'; \
    wget https://www.python.org/ftp/python/3.5.1/python-3.5.1.exe -OutFile c:\python-3.5.1.exe ; \
    Start-Process c:\python-3.5.1.exe -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait ; \
    Remove-Item c:\python-3.5.1.exe -Force

#   Chocolate
RUN powershell.exe -Command \
    $ErrorActionPreference = 'Stop'; \
    "iwr https://chocolatey.org/install.ps1 -UseBasicParsing | iex"

#   Git (using Chocolate)
RUN powershell.exe -Command \
    $ErrorActionPreference = 'Stop'; \
    choco install git  -ArgumentList '-params /GitAndUnixTllsOnPath' -y -Wait

#   PIP deps
RUN powershell.exe -Command \
    $ErrorActionPreference = 'Stop'; \
    pip install -U pip pytest
