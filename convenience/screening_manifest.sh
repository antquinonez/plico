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
MANIFEST_DIR="./manifests/manifest_screening_skills_$(date +%Y%m%d%H%M%S)"
python scripts/create_screening_manifest.py "$MANIFEST_DIR" \
  --jd ./library/job_descriptions/Sample_JD_Google_Data_Engineer.md \
  --resumes-path "$RESUMES" \
  --planning \
  --planning-client litellm-mistral-large \
  --planning-prompts screening_skills_planning \
  --synthesis-prompts screening_synthesis
python scripts/manifest_run.py "$MANIFEST_DIR" \
  --documents-path "$RESUMES" -c 5
