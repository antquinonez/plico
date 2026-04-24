#!/usr/bin/env bash
set -euo pipefail
RESUMES="./library/resumes/"
PRESCREEN_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    small|medium)
      if [ "$1" = "small" ]; then RESUMES="./library/resumes_small/"; fi
      if [ "$1" = "medium" ]; then RESUMES="./library/resumes_medium/"; fi
      shift
      ;;
    --pre-screen)
      shift
      if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^- ]]; then
        PRESCREEN_FLAG="--pre-screen $1"
        shift
      else
        echo "Error: --pre-screen requires a number (e.g., --pre-screen 10)"
        exit 1
      fi
      ;;
    *)
      echo "Usage: $0 [small|medium] [--pre-screen [N]]"
      echo ""
      echo "Resume set:"
      echo "  (no argument)      Full set (library/resumes/)"
      echo "  small              Small set (library/resumes_small/)"
      echo "  medium             Medium set (library/resumes_medium/)"
      echo ""
      echo "Pre-screening:"
      echo "  --pre-screen 10    Enable pre-screening with top-K candidates"
      exit 1
      ;;
  esac
done

WORKBOOK="screening_$(date +%Y%m%d%H%M%S).xlsx"
python scripts/create_screening_workbook.py "./$WORKBOOK" \
  --jd ./library/job_descriptions/Sample_JD_Google_Data_Engineer.md \
  --resumes-path "$RESUMES" \
  --planning \
  --planning-client litellm-mistral-large \
  --planning-prompts screening_skills_planning \
  --synthesis-prompts screening_synthesis \
  $PRESCREEN_FLAG

python scripts/run_orchestrator.py "./$WORKBOOK" -c 5
