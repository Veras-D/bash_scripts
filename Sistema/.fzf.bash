# Setup fzf
# ---------
if [[ ! "$PATH" == */home/veras/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/veras/.fzf/bin"
fi

# Auto-completion
# ---------------
source "/home/veras/.fzf/shell/completion.bash"

# Key bindings
# ------------
source "/home/veras/.fzf/shell/key-bindings.bash"
