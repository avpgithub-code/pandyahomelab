#!/bin/bash
# scaffold-platform.sh
#
# Creates the pandyaHomeLab platform folder structure per ADR-007.
# Run this ONCE from /volume1/pandya-homelab/ before initial Git commit.
#
# After running, the platform tree should look like:
#
#   /volume1/pandya-homelab/
#   ├── platform/
#   │   ├── proxy/      (.gitkeep)
#   │   ├── data/       (.gitkeep)
#   │   └── mlops/      (.gitkeep)
#   ├── site/
#   │   ├── apex/       (.gitkeep)
#   │   ├── ml/         (.gitkeep)
#   │   ├── dl/         (.gitkeep)
#   │   ├── nlp/        (.gitkeep)
#   │   └── agentic/    (.gitkeep)
#   ├── services/
#   │   ├── ml/         (.gitkeep)
#   │   ├── dl/         (.gitkeep)
#   │   ├── nlp/        (.gitkeep)
#   │   └── agentic/    (.gitkeep)
#   ├── compose/        (.gitkeep)
#   └── docs/           (already populated)

set -euo pipefail

PLATFORM_ROOT="/volume1/pandya-homelab"

# Verify we're running from the right place
if [ "$(pwd)" != "$PLATFORM_ROOT" ]; then
    echo "Error: This script must be run from $PLATFORM_ROOT"
    echo "Currently at: $(pwd)"
    exit 1
fi

echo "Scaffolding pandyaHomeLab platform structure at $PLATFORM_ROOT"
echo ""

# Platform tier — services that support the demos
echo "Creating platform/ tier..."
mkdir -p platform/proxy
mkdir -p platform/data
mkdir -p platform/mlops
touch platform/proxy/.gitkeep
touch platform/data/.gitkeep
touch platform/mlops/.gitkeep
echo "  ✓ platform/{proxy,data,mlops}/"

# Site tier — static L1-L3 content per ADR-003 URL hierarchy
echo "Creating site/ tier..."
mkdir -p site/apex
mkdir -p site/ml
mkdir -p site/dl
mkdir -p site/nlp
mkdir -p site/agentic
touch site/apex/.gitkeep
touch site/ml/.gitkeep
touch site/dl/.gitkeep
touch site/nlp/.gitkeep
touch site/agentic/.gitkeep
echo "  ✓ site/{apex,ml,dl,nlp,agentic}/"

# Services tier — per-domain demos
echo "Creating services/ tier..."
mkdir -p services/ml
mkdir -p services/dl
mkdir -p services/nlp
mkdir -p services/agentic
touch services/ml/.gitkeep
touch services/dl/.gitkeep
touch services/nlp/.gitkeep
touch services/agentic/.gitkeep
echo "  ✓ services/{ml,dl,nlp,agentic}/"

# Compose — docker-compose files (single folder, no children yet)
echo "Creating compose/..."
mkdir -p compose
touch compose/.gitkeep
echo "  ✓ compose/"

# Verification
echo ""
echo "Scaffolding complete. Final structure:"
echo ""
find . -maxdepth 2 -type d ! -path '*/\.*' ! -path '*/\#*' | sort

echo ""
echo "Next steps:"
echo "  1. Verify README.md and .gitignore are at $PLATFORM_ROOT"
echo "  2. Run: git init"
echo "  3. Run: git add -A && git status"
echo "  4. If status looks right: git commit -m 'Stage 2 architectural baseline'"
echo "  5. Configure remote and push: git remote add origin <github-url> && git push -u origin main"
echo "  6. Tag the baseline: git tag stage-2-baseline && git push origin stage-2-baseline"
