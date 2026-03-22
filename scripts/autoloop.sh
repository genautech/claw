#!/usr/bin/env bash
# ============================================================
# Agência Autônoma - Loop Perpétuo
# ============================================================
# Mantém todas as IAs (PolyClaw, PolyWhale, Ninja, Executor)
# acordando, trabalhando e dormindo ritmicamente.
# ============================================================

INTERVALO_SEG=900 # 15 minutos por padrão
CICLO=1

echo "==========================================================="
echo " 🐋 Iniciando Agência Autônoma (Ciclos a cada $((INTERVALO_SEG / 60)) min)"
echo "==========================================================="

while true; do
  echo ""
  echo "==========================================================="
  echo " 🔄 CICLO $CICLO - $(date)"
  echo "==========================================================="
  
  bash scripts/run-agents.sh all
  
  echo ""
  echo "💤 Ciclo $CICLO completo."
  
  # Cronômetro visual de contagem regressiva
  for (( i=INTERVALO_SEG; i>0; i--)); do
    min=$((i / 60))
    sec=$((i % 60))
    printf "\r⏳ O próximo ciclo (Ciclo %d) começa em: %02d:%02d... " $((CICLO + 1)) $min $sec
    sleep 1
  done
  
  printf "\n"
  ((CICLO++))
done
