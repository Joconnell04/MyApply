#!/bin/bash
# Verification script for AgentKit integration

set -e

echo "🔍 Verifying AgentKit Integration..."
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
checks_passed=0
checks_total=0

# Helper function
check_file() {
    checks_total=$((checks_total + 1))
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} Found: $1"
        checks_passed=$((checks_passed + 1))
        return 0
    else
        echo -e "${RED}✗${NC} Missing: $1"
        return 1
    fi
}

# Check core files
echo "📁 Checking core integration files..."
check_file "applications.py"
check_file "workflow_constants.py"
check_file "routers/jd_ingest.py"
check_file "routers/resume_build.py"
check_file "services/openai_workflows.py"
check_file "models.py"
check_file "app.py"

echo ""
echo "📚 Checking documentation files..."
check_file "README.md"
check_file "DEPLOYMENT.md"

echo ""
echo "🧪 Checking test files..."
check_file "tests/test_workflows.py"
check_file "tests/__init__.py"

echo ""
echo "🔧 Checking configuration files..."
check_file ".env.example"
check_file "requirements.txt"

echo ""
echo "🔍 Checking for required patterns in files..."

# Check if models.py contains WorkflowRun
checks_total=$((checks_total + 1))
if grep -q "class WorkflowRun" models.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} WorkflowRun model found in models.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} WorkflowRun model not found in models.py"
fi

# Check if models.py contains Artifact
checks_total=$((checks_total + 1))
if grep -q "class Artifact" models.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Artifact model found in models.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} Artifact model not found in models.py"
fi

# Check if app.py includes CORS
checks_total=$((checks_total + 1))
if grep -q "CORSMiddleware" app.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} CORS middleware configured in app.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} CORS middleware not found in app.py"
fi

# Check if app.py includes routers
checks_total=$((checks_total + 1))
if grep -q "from routers.jd_ingest import router" app.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} JD ingest router imported in app.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} JD ingest router not imported in app.py"
fi

checks_total=$((checks_total + 1))
if grep -q "from routers.resume_build import router" app.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Resume build router imported in app.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} Resume build router not imported in app.py"
fi

# Check if requirements.txt includes pytest
checks_total=$((checks_total + 1))
if grep -q "pytest" requirements.txt 2>/dev/null; then
    echo -e "${GREEN}✓${NC} pytest added to requirements.txt"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} pytest not found in requirements.txt"
fi

# Check for workflow IDs in workflow_constants.py
checks_total=$((checks_total + 1))
if grep -q "wf_68ec6800d1948190a0629c0eaf07f8e303633b84fcb85ab9" workflow_constants.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} ResumeBuilderV2 workflow ID found in workflow_constants.py"
    checks_passed=$((checks_passed + 1))
else
    echo -e "${RED}✗${NC} ResumeBuilderV2 workflow ID not found in workflow_constants.py"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo ""
echo "☁️  Checking Railway deployment files..."
check_file "Procfile"
check_file "railway.json"
check_file "runtime.txt"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $checks_passed -eq $checks_total ]; then
    echo -e "${GREEN}✅ All checks passed! ($checks_passed/$checks_total)${NC}"
    echo ""
    echo "🚀 Your MyApply platform is ready!"
    echo ""
    echo "📦 Local Development:"
    echo "  1. pip install -r requirements.txt"
    echo "  2. cp .env.example .env (add OPENAI_API_KEY)"
    echo "  3. pytest -v"
    echo "  4. uvicorn app:app --reload"
    echo ""
    echo "☁️  Railway Deployment:"
    echo "  1. Push to GitHub"
    echo "  2. Create Railway project from repo"
    echo "  3. Add PostgreSQL database"
    echo "  4. Set environment variables (see DEPLOYMENT.md)"
    echo "  5. Deploy automatically on push"
    echo ""
    echo "📖 Documentation:"
    echo "  - README.md - Features & quick start"
    echo "  - DEPLOYMENT.md - Full deployment guide"
    exit 0
else
    echo -e "${RED}⚠️  Some checks failed ($checks_passed/$checks_total passed)${NC}"
    echo ""
    echo "Please review the missing items above."
    exit 1
fi
