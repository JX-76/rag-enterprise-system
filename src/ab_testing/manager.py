"""
A/B Test Manager - A/B测试管理器
支持实验管理、流量分配、指标追踪
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import random
import asyncio
from pathlib import Path
from enum import Enum

from src.core.logging import get_logger

logger = get_logger(__name__)


class ExperimentStatus(Enum):
    """实验状态"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class Variant:
    """实验变体"""
    id: str
    name: str
    config: Dict[str, Any]
    traffic_percentage: float  # 0-100
    metrics: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class Experiment:
    """实验"""
    id: str
    name: str
    description: str
    variants: List[Variant]
    status: ExperimentStatus
    created_at: datetime
    ended_at: Optional[datetime] = None
    target_metric: str = "conversion"
    min_sample_size: int = 100
    winner: Optional[str] = None


class ABTestManager:
    """
    A/B测试管理器
    
    功能：
    1. 创建和管理实验
    2. 流量分配
    3. 指标收集
    4. 统计显著性计算
    5. 自动决策
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or "./data/ab_tests.json"
        self._experiments: Dict[str, Experiment] = {}
        self._user_assignments: Dict[str, str] = {}  # user_id -> variant_id
        self._lock = asyncio.Lock()
        self._load_experiments()
    
    def _load_experiments(self):
        """加载实验"""
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for exp_data in data.get('experiments', []):
                        exp = self._dict_to_experiment(exp_data)
                        self._experiments[exp.id] = exp
                logger.info(f"Loaded {len(self._experiments)} experiments")
        except Exception as e:
            logger.error(f"Failed to load experiments: {e}")
    
    def _save_experiments(self):
        """保存实验"""
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'experiments': [
                    self._experiment_to_dict(exp) for exp in self._experiments.values()
                ]
            }
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save experiments: {e}")
    
    def _dict_to_experiment(self, data: Dict) -> Experiment:
        """字典转实验"""
        variants = [
            Variant(
                id=v['id'],
                name=v['name'],
                config=v['config'],
                traffic_percentage=v['traffic_percentage'],
                metrics=v.get('metrics', {})
            )
            for v in data['variants']
        ]
        
        return Experiment(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            variants=variants,
            status=ExperimentStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            ended_at=datetime.fromisoformat(data['ended_at']) if data.get('ended_at') else None,
            target_metric=data.get('target_metric', 'conversion'),
            min_sample_size=data.get('min_sample_size', 100),
            winner=data.get('winner')
        )
    
    def _experiment_to_dict(self, exp: Experiment) -> Dict:
        """实验转字典"""
        return {
            'id': exp.id,
            'name': exp.name,
            'description': exp.description,
            'variants': [
                {
                    'id': v.id,
                    'name': v.name,
                    'config': v.config,
                    'traffic_percentage': v.traffic_percentage,
                    'metrics': v.metrics
                }
                for v in exp.variants
            ],
            'status': exp.status.value,
            'created_at': exp.created_at.isoformat(),
            'ended_at': exp.ended_at.isoformat() if exp.ended_at else None,
            'target_metric': exp.target_metric,
            'min_sample_size': exp.min_sample_size,
            'winner': exp.winner
        }
    
    def _hash_user(self, user_id: str, experiment_id: str) -> float:
        """哈希用户ID到0-1范围"""
        hash_input = f"{experiment_id}:{user_id}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        return int(hash_value, 16) / (2**128)
    
    async def create_experiment(
        self,
        name: str,
        description: str,
        variants_config: List[Dict[str, Any]],
        target_metric: str = "conversion"
    ) -> Experiment:
        """创建实验"""
        import uuid
        
        exp_id = f"exp_{uuid.uuid4().hex[:12]}"
        
        # 创建变体
        variants = []
        total_traffic = 0
        
        for i, config in enumerate(variants_config):
            variant = Variant(
                id=f"{exp_id}_v{i}",
                name=config['name'],
                config=config['config'],
                traffic_percentage=config['traffic_percentage']
            )
            variants.append(variant)
            total_traffic += config['traffic_percentage']
        
        # 校验流量分配
        if abs(total_traffic - 100) > 0.01:
            raise ValueError(f"Traffic percentages must sum to 100, got {total_traffic}")
        
        experiment = Experiment(
            id=exp_id,
            name=name,
            description=description,
            variants=variants,
            status=ExperimentStatus.DRAFT,
            created_at=datetime.now(),
            target_metric=target_metric
        )
        
        async with self._lock:
            self._experiments[exp_id] = experiment
            self._save_experiments()
        
        logger.info(f"Created experiment: {exp_id}")
        return experiment
    
    async def get_variant(self, experiment_id: str, user_id: str) -> Optional[Variant]:
        """为用户分配变体"""
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # 检查是否已有分配
        assignment_key = f"{experiment_id}:{user_id}"
        if assignment_key in self._user_assignments:
            variant_id = self._user_assignments[assignment_key]
            for variant in experiment.variants:
                if variant.id == variant_id:
                    return variant
        
        # 新分配
        hash_value = self._hash_user(user_id, experiment_id)
        cumulative = 0
        
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage / 100
            if hash_value <= cumulative:
                self._user_assignments[assignment_key] = variant.id
                return variant
        
        # 默认返回最后一个
        return experiment.variants[-1]
    
    async def record_metric(
        self,
        experiment_id: str,
        variant_id: str,
        metric_name: str,
        value: float
    ):
        """记录指标"""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return
        
        for variant in experiment.variants:
            if variant.id == variant_id:
                if metric_name not in variant.metrics:
                    variant.metrics[metric_name] = []
                variant.metrics[metric_name].append(value)
                break
    
    async def start_experiment(self, experiment_id: str) -> bool:
        """启动实验"""
        async with self._lock:
            if experiment_id not in self._experiments:
                return False
            
            exp = self._experiments[experiment_id]
            exp.status = ExperimentStatus.RUNNING
            self._save_experiments()
            
            logger.info(f"Started experiment: {experiment_id}")
            return True
    
    async def stop_experiment(self, experiment_id: str, winner_id: Optional[str] = None) -> bool:
        """停止实验"""
        async with self._lock:
            if experiment_id not in self._experiments:
                return False
            
            exp = self._experiments[experiment_id]
            exp.status = ExperimentStatus.COMPLETED
            exp.ended_at = datetime.now()
            exp.winner = winner_id
            self._save_experiments()
            
            logger.info(f"Stopped experiment: {experiment_id}, winner: {winner_id}")
            return True
    
    async def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """获取实验结果"""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return {}
        
        results = {
            'experiment_id': experiment_id,
            'name': experiment.name,
            'status': experiment.status.value,
            'target_metric': experiment.target_metric,
            'variants': []
        }
        
        for variant in experiment.variants:
            metrics_data = variant.metrics.get(experiment.target_metric, [])
            
            variant_result = {
                'id': variant.id,
                'name': variant.name,
                'traffic_percentage': variant.traffic_percentage,
                'sample_size': len(metrics_data),
                'mean': sum(metrics_data) / len(metrics_data) if metrics_data else 0,
                'total': sum(metrics_data) if metrics_data else 0
            }
            
            results['variants'].append(variant_result)
        
        return results


# 全局实例
_ab_test_manager: Optional[ABTestManager] = None


async def get_ab_test_manager() -> ABTestManager:
    """获取全局A/B测试管理器"""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager
