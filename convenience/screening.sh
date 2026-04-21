#!/usr/bin/env bash
set -euo pipefail
SIZE="${1:-}"
case "$SIZE" in
  small)  RESUMES="./library/resumes_small/" ;;
  medium) RESUMES="./library/resumes_medium/" ;;
  "")     RESUMES="./library/resumes/" ;;
  *)
    echo "Usage: $0 [small|medium]"
    echo "  (no argument = full resume set)"
    exit 1
    ;;
esac
WORKBOOK="screening_$(date +%Y%m%d%H%M%S).xlsx"
python scripts/create_screening_workbook.py "./$WORKBOOK" \
  --jd ./library/job_descriptions/Sample_JD_Google_Data_Engineer.md \
  --resumes-path "$RESUMES" \
  --planning \
  --planning-prompts screening_skills_planning \
  --synthesis-prompts screening_synthesis
python scripts/run_orchestrator.py "./$WORKBOOK" -c 5
