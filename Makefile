# RAG Enterprise System - Makefile

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: help install test lint format docker k8s clean smoke eval-repo mvp-check

# 默认目标
help:
	@echo "RAG Enterprise System - 可用命令:"
	@echo "  make install     - 安装依赖"
	@echo "  make install-dev - 安装开发依赖"
	@echo "  make test        - 运行测试"
	@echo "  make test-cov    - 运行测试并生成覆盖率报告"
	@echo "  make lint        - 代码检查"
	@echo "  make format      - 代码格式化"
	@echo "  make smoke       - 运行无服务 validation smoke"
	@echo "  make eval-repo   - 运行 repo-grounded evaluation"
	@echo "  make mvp-check   - 执行最小 MVP 自检路径"
	@echo "  make docker      - 构建Docker镜像"
	@echo "  make docker-run  - 运行Docker容器"
	@echo "  make k8s-deploy  - 部署到Kubernetes"
	@echo "  make k8s-delete  - 删除Kubernetes部署"
	@echo "  make locust      - 运行Locust压测"
	@echo "  make clean       - 清理临时文件"

# 安装依赖
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-full.txt
	pre-commit install

# 测试
test:
	$(PYTHON) -m pytest tests/unit/ -v

test-cov:
	$(PYTHON) -m pytest tests/unit/ -v --cov=src --cov-report=html --cov-report=term

# 代码质量
lint:
	flake8 src/ tests/
	mypy src/
	bandit -r src/

format:
	black src/ tests/
	isort src/ tests/

format-check:
	black --check src/ tests/
	isort --check-only src/ tests/

# Validation / Evaluation
smoke:
	$(PYTHON) scripts/run_validation_smoke.py

eval-repo:
	$(PYTHON) scripts/run_repo_grounded_eval.py

mvp-check: smoke
	@echo "MVP smoke path complete. Review artifacts under artifacts/eval/."

# Docker
docker:
	docker build -t rag-enterprise-system:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

# Kubernetes
k8s-deploy:
	kubectl apply -f k8s/
	kubectl apply -f k8s/ingress.yaml

k8s-delete:
	kubectl delete -f k8s/

k8s-status:
	kubectl get pods -l app=rag-api
	kubectl get svc rag-api

# Helm
helm-install:
	helm install rag ./helm

helm-upgrade:
	helm upgrade rag ./helm

helm-delete:
	helm delete rag

# 压测
locust:
	locust -f locustfile.py --host=http://localhost:8000

# 清理
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf build/
	rm -rf dist/

# 开发运行
dev:
	$(PYTHON) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 生产运行
prod:
	gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
