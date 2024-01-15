#!/usr/bin/env bash

sudo apt update && sudo apt upgrade
sudo apt install lollypop
sudo apt install vlc
sudo apt install npm
sudo apt install snapd
sudo snap install pycharm-community --classic
sudo apt install code
code --install-extension 076923.python-image-preview 0h7z.vscode-julia-format 4a454646.github-purple AffenWiesel.matlab-formatter apommel.matlab-interactive-terminal batisteo.vscode-django bbenoist.shell benjamin-simmonds.pythoncpp-debug Blackboxapp.blackbox bmalehorn.shell-syntax bramvanbilsen.matlab-code-run corker.vscode-micromamba cstrap.python-snippets danielpinto8zz6.c-cpp-compile-run donjayamanne.python-environment-manager donjayamanne.python-extension-pack dracula-theme.theme-dracula eamodio.gitlens emmanuelbeziat.vscode-great-icons esbenp.prettier-vscode firefox-devtools.vscode-firefox-debug formulahendry.auto-rename-tag formulahendry.code-runner fortran-lang.linter-gfortran foxundermoon.shell-format Gimly81.fortran Gimly81.matlab GitHub.vscode-pull-request-github graykode.ai-docstring HarryHopkinson.vs-code-runner julialang.language-julia KevinRose.vsc-python-indent mads-hartmann.bash-ide-vscode ms-azuretools.vscode-docker MS-CEINTL.vscode-language-pack-pt-BR ms-python.pylint ms-python.python ms-python.vscode-pylance ms-toolsai.jupyter ms-toolsai.jupyter-keymap ms-toolsai.jupyter-renderers ms-toolsai.vscode-jupyter-cell-tags ms-toolsai.vscode-jupyter-slideshow ms-vscode.cmake-tools ms-vscode.cpptools ms-vscode.cpptools-extension-pack ms-vscode.cpptools-themes njpwerner.autodocstring njqdev.vscode-python-typehint paulosilva.vsc-octave-debugger Remisa.shellman ritwickdey.LiveServer RobbOwen.synthwave-vscode rocketseat.theme-omni rogalmic.bash-debug skyran.matlab-snippets Slaier.matlab-complete streetsidesoftware.code-spell-checker streetsidesoftware.code-spell-checker-portuguese-brazilian tal7aouy.icons tianjiaohuang.octave-debug twxs.cmake VisualStudioExptTeam.intellicode-api-usage-examples VisualStudioExptTeam.vscodeintellicode vscode-icons-team.vscode-icons wholroyd.jinja
sudo apt install mpv

sudo apt autoremove && sudo apt autoclean && sudo apt clean
flatpak update
snap refresh
