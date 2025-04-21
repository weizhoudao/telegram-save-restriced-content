import time
import threading

class SnowflakeGenerator:
    def __init__(self, machine_id: int, epoch: int = 1609459200000):
        """
        machine_id : 机器ID (0-1023)
        epoch     : 起始时间戳（毫秒），默认2021-01-01 00:00:00 UTC
        """
        if not 0 <= machine_id < 1024:
            raise ValueError("Machine ID must be between 0 and 1023")
        self.machine_id = machine_id
        self.epoch = epoch
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def generate_id(self) -> int:
        with self.lock:
            timestamp = self._current_time()
            if timestamp < self.last_timestamp:
                raise ValueError("Clock moved backwards, rejecting ID generation.")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF  # 12位序列号
                if self.sequence == 0:  # 当前毫秒序列号耗尽
                    timestamp = self._wait_next_millis()
            else:
                self.sequence = 0

            self.last_timestamp = timestamp
            return ((timestamp - self.epoch) << 22) | (self.machine_id << 12) | self.sequence

    def _current_time(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_millis(self) -> int:
        timestamp = self._current_time()
        while timestamp <= self.last_timestamp:
            time.sleep(0.001)
            timestamp = self._current_time()
        return timestamp
# 使用示例（全局单例）
#_generator = SnowflakeGenerator(machine_id=1)  # 确保不同机器使用不同ID
