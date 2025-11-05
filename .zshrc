
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/opt/anaconda3/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]; then
        . "/opt/anaconda3/etc/profile.d/conda.sh"
    else
        export PATH="/opt/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

export PATH="/opt/homebrew/bin:$PATH"
export ODBCSYSINI="/opt/homebrew/etc"
export ODBCINSTINI="/opt/homebrew/etc/odbcinst.ini"
export DC_DB_STRING_MASTER="DRIVER={ODBC Driver 18 for SQL Server};SERVER=sqls-dclab.database.windows.net,1433;DATABASE=dclab;UID=ducle@dragoncapital.com;Authentication=ActiveDirectoryInteractive;"

