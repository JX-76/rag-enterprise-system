.PHONY: help install install-dev test test-unit test-integration test-benchmark lint format clean docker-build docker-run k8s-deploy

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:  ## Run all tests
	pytest tests/ -v

test-unit:  ## Run unit tests
	pytest tests/unit -v --cov=src --cov-report=html --cov-report=term

test-integration:  ## Run integration tests
	pytest tests/integration -v

test-benchmark:  ## Run benchmark tests
	pytest tests/benchmark -v -m benchmark

lint:  ## Run linting checks
	flake8 src tests --count --show-source --statistics
	mypy src --ignore-missing-imports

format:  ## Format code with black and isort
	black src tests
	isort src tests

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:  ## Build Docker image
	docker build -f deploy/docker/Dockerfile -t rag-enterprise:latest .

docker-run:  ## Run with Docker Compose
	docker-compose up -d

docker-stop:  ## Stop Docker Compose
	docker-compose down

k8s-deploy:  ## Deploy to Kubernetes
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/configmap.yaml
	kubectl apply -f deploy/k8s/secret.yaml
	kubectl apply -f deploy/k8s/deployment.yaml
	kubectl apply -f deploy/k8s/service.yaml
	kubectl apply -f deploy/k8s/ingress.yaml

k8s-delete:  ## Delete from Kubernetes
	kubectl delete -f deploy/k8s/

run:  ## Run development server
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

run-prod:  ## Run production server
	gunicorn -k uvicorn.workers.UvicornWorker -c config/gunicorn.conf.py src.main:app

docs-serve:  ## Serve documentation locally
	mkdocs serve

docs-build:  ## Build documentation
	mkdocs build

benchmark:  ## Run performance benchmark
	python scripts/benchmark.py --qps 100 --duration 60

evaluate:  ## Run evaluation
	python scripts/evaluate.py --dataset data/eval_dataset.json
