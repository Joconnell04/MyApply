#!/bin/bash
# Test script for AgentKit integration

set -e

echo "🧪 Testing AgentKit Integration..."
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected."
    echo "   Consider running: python -m venv venv && source venv/bin/activate"
    echo ""
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "📦 Installing test dependencies..."
    pip install pytest pytest-cov
    echo ""
fi

# Run the tests
echo "🔬 Running AgentKit route tests..."
pytest tests/test_agentkit_routes.py -v --color=yes

echo ""
echo "✅ Tests complete!"
