#!/bin/bash

# 配置部分（根据实际情况修改）
PYTHON_SCRIPT="devgagan"  # Python脚本路径
LOG_FILE="./savedog.log"        # 日志文件路径
PYTHON_EXEC="python3.13"                    # Python解释器路径

# 定义启动函数
start() {
    # 检查是否已经运行
    if pgrep -f "$PYTHON_SCRIPT" >/dev/null; then
        echo "Python脚本已经在运行中"
        return 1
    fi
    
    # 启动脚本并重定向输出到日志文件
    echo "正在启动Python脚本..."
	source ./.env
    nohup $PYTHON_EXEC -m "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1 &
    
    # 等待1秒确认启动
    sleep 1
    if pgrep -f "$PYTHON_SCRIPT" >/dev/null; then
        echo "成功启动 | PID: $(pgrep -f "$PYTHON_SCRIPT") | 日志: $LOG_FILE"
    else
        echo "启动失败，请检查日志: $LOG_FILE"
    fi
}

# 定义停止函数
stop() {
    local pids
    pids=$(pgrep -f "$PYTHON_SCRIPT")
    
    if [ -z "$pids" ]; then
        echo "Python脚本未在运行"
        return 1
    fi

    echo "正在停止Python脚本 (PID: $pids)..."
    kill -TERM $pids >/dev/null 2>&1
    
    # 等待最多5秒直到进程结束
    local timeout=5
    while [ $timeout -gt 0 ] && pgrep -f "$PYTHON_SCRIPT" >/dev/null; do
        sleep 1
        ((timeout--))
    done

    if [ $timeout -eq 0 ]; then
        echo "强制杀死进程..."
        kill -KILL $pids >/dev/null 2>&1
        sleep 1
    fi
    
    echo "已停止"
}

# 定义重启函数
restart() {
    stop
    start
}

# 命令解析
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    *)
        echo "用法: $0 {start|stop|restart}"
        exit 1
esac

exit 0
