#!/bin/bash

echo "🚀 Period GPT2 - Quick Deployment Helper"
echo "========================================"
echo ""
echo "This script helps you prepare for deployment."
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "⚠️  Git not initialized. Initializing..."
    git init
    echo "✅ Git initialized"
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  You have uncommitted changes."
    read -p "Do you want to commit them now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        git commit -m "Prepare for deployment"
        echo "✅ Changes committed"
    fi
fi

echo ""
echo "📋 Deployment Checklist:"
echo "1. ✅ Code is committed to Git"
echo "2. ⬜ Push to GitHub/GitLab/Bitbucket"
echo "3. ⬜ Deploy backend to Railway (recommended) or Render"
echo "4. ⬜ Deploy frontend to Vercel"
echo "5. ⬜ Set environment variables"
echo "6. ⬜ Update CORS settings"
echo ""
echo "📖 See DEPLOY.md for detailed instructions"
echo ""
echo "Ready to deploy! 🎉"
