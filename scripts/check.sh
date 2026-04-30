#!/bin/bash

echo "Running local checks..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Terraform format
echo "Checking Terraform format..."
terraform fmt -check -recursive
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Terraform format: OK${NC}"
else
    echo -e "${RED}Terraform format: FAILED${NC}"
    exit 1
fi

# 2. Terraform validate
echo "Validating Terraform..."
terraform init -backend=false > /dev/null 2>&1
terraform validate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Terraform validate: OK${NC}"
else
    echo -e "${RED}Terraform validate: FAILED${NC}"
    exit 1
fi

# 3. Dockerfile lint
echo "Checking Dockerfile..."
docker run --rm -i hadolint/hadolint < app/Dockerfile
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Dockerfile: OK${NC}"
else
    echo -e "${RED}❌ Dockerfile: WARNINGS${NC}"
fi

# 4. Python security
echo "Checking Python dependencies..."
pip install pip-audit -q
pip-audit --requirement app/requirements.txt --desc 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Python deps: OK${NC}"
else
    echo -e "${RED}Python deps: VULNERABILITIES${NC}"
fi

echo -e "${GREEN}All checks completed!${NC}"
