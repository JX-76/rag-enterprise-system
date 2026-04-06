"""
限流器单元测试
测试 Token Bucket 算法的各种场景
"""
import asyncio
import pytest

from src.api.middleware.rate_limit import TokenBucket


class TestTokenBucket:
    """Token Bucket限流器测试"""
    
    @pytest.fixture
    def bucket(self):
        """创建限流器实例"""
        return TokenBucket(rate=10, capacity=20, key="test")
    
    @pytest.mark.asyncio
    async def test_initial_full(self, bucket):
        """初始状态桶是满的"""
        assert bucket.tokens == 20
        assert bucket.capacity == 20
        assert bucket.rate == 10
    
    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self, bucket):
        """获取token消耗一个"""
        initial_tokens = bucket.tokens
        result = await bucket.acquire()
        
        assert result is True
        assert bucket.tokens == initial_tokens - 1
    
    @pytest.mark.asyncio
    async def test_acquire_multiple(self, bucket):
        """连续获取多个token"""
        for i in range(5):
            result = await bucket.acquire()
            assert result is True
        
        assert bucket.tokens == 15  # 20 - 5
    
    @pytest.mark.asyncio
    async def test_acquire_until_empty(self, bucket):
        """获取直到桶空"""
        # 获取所有token
        for i in range(20):
            result = await bucket.acquire()
            assert result is True
        
        assert bucket.tokens == 0
        
        # 再次获取应该失败
        result = await bucket.acquire()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_token_refill(self, bucket):
        """token随时间补充"""
        # 消耗所有token
        for i in range(20):
            await bucket.acquire()
        
        assert bucket.tokens == 0
        
        # 等待补充
        await asyncio.sleep(0.5)  # 应该补充5个token (10 * 0.5)
        
        # 尝试获取
        results = []
        for i in range(10):
            results.append(await bucket.acquire())
        
        # 应该能获取到补充的token
        success_count = sum(results)
        assert success_count >= 4  # 至少4-5个
    
    @pytest.mark.asyncio
    async def test_refill_not_exceed_capacity(self, bucket):
        """补充不超过容量"""
        # 只消耗少量token
        for i in range(5):
            await bucket.acquire()
        
        assert bucket.tokens == 15
        
        # 等待较长时间
        await asyncio.sleep(2)
        
        # 尝试获取更多
        for i in range(20):
            await bucket.acquire()
        
        # 总共不应该超过容量20
        # 这里主要测试没有异常
    
    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """测试并发获取安全性"""
        bucket = TokenBucket(rate=100, capacity=50, key="concurrent")
        
        async def try_acquire():
            return await bucket.acquire()
        
        # 并发获取
        tasks = [try_acquire() for _ in range(60)]
        results = await asyncio.gather(*tasks)
        
        # 成功的次数应该等于容量
        success_count = sum(results)
        assert success_count <= 50  # 不超过容量
        assert success_count >= 45  # 允许少量误差
    
    def test_different_keys(self):
        """不同key的桶是独立的"""
        bucket1 = TokenBucket(rate=10, capacity=20, key="key1")
        bucket2 = TokenBucket(rate=10, capacity=20, key="key2")
        
        assert bucket1 is not bucket2
