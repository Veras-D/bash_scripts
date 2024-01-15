#!/usr/bin/env bash

# Variaveis
data=$( date +%Y-%m-%d )

header="#!/usr/bin/env bash
# -----------------------------------------------------------
# Script   :
# Descrição:
# Versão   : 0.1
# Autor    : Veras-D <dveras2310@gmail.com>
# Data     : $data
Licança    : GNU/GPL v3.0
-------------------------------------------------------------
# Uso      :
# -----------------------------------------------------------
"
erro1="O script só aceita UM unico argumento."
erro2="Nome do argumento é um arquivo já existente."
# Testando numero de argumentos
[[ $# -ne 1 ]] && echo "$erro1" && exit 1

# Testeando se o arquivo já existe
[[ -f $1 ]] && echo "$erro2" && exit 1

# Executando o comando
echo "$header" > $1 && chmod +x $1 && nano $1

exit 0 
