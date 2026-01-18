"""
Protocol Core Service
1052Bot 协议的核心服务层。
提供 HTTP 接口以接收外部指令。
"""

import asyncio
import logging
from flask import Flask, request, jsonify
from .system_bridge import SystemBridge

# 初始化 Flask 应用
core_app = Flask(__name__)

# 初始化系统桥接器
# 注意：在 Flask 启动前初始化，但具体的窗口查找是每次请求时动态进行的
bridge_instance = SystemBridge()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProtocolCore")

@core_app.route('/api/dispatch', methods=['POST'])
def dispatch_directive():
    """
    指令分发接口。
    
    请求格式示例:
    {
        "directive": "transmit_msg",
        "arguments": {
            "target": "FileTransferAssistant",
            "content": "Hello from 1052Bot"
        }
    }
    """
    try:
        data_packet = request.get_json()
        if not data_packet:
            return jsonify({"outcome": "error", "details": "invalid_json"}), 400
        
        directive_type = data_packet.get("directive")
        args = data_packet.get("arguments", {})
        
        logger.info(f"Received directive: {directive_type}")
        
        if directive_type == "transmit_msg":
            target = args.get("target")
            content = args.get("content")
            
            if not target or not content:
                return jsonify({"outcome": "error", "details": "missing_arguments"}), 400
            
            # 由于 SystemBridge 使用 async，我们需要在这里运行它
            # Flask 是同步的，我们使用 asyncio.run 来执行异步任务
            # 注意：在高并发下可能需要更复杂的处理，但对于单线程自动化足够了
            result_report = asyncio.run(bridge_instance.dispatch_payload(target, content))
            
            if result_report.get("success_flag"):
                return jsonify({"outcome": "success", "report": result_report})
            else:
                return jsonify({"outcome": "failure", "report": result_report}), 500
                
        else:
            return jsonify({"outcome": "error", "details": "unknown_directive"}), 404
            
    except Exception as e:
        logger.error(f"Core execution error: {e}")
        return jsonify({"outcome": "error", "details": str(e)}), 500

def ignite_core(port=10520):
    """启动协议核心服务。"""
    logger.info(f"Igniting 1052Bot Protocol Core on port {port}...")
    core_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    ignite_core()
