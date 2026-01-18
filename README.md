# 1052Bot Protocol

这是一个全新的协议实现，旨在提供基于 HTTP 的自动化消息传输服务。

## 协议规范

本协议采用 HTTP POST 方式进行通信。所有字段命名均遵循 1052Bot 独有规范。

### 接口地址
`POST /api/dispatch`

### 请求格式 (JSON)
```json
{
    "directive": "transmit_msg",
    "arguments": {
        "target": "目标联系人或群名称",
        "content": "消息内容"
    }
}
```

### 响应格式 (JSON)
成功：
```json
{
    "outcome": "success",
    "report": {
        "success_flag": true,
        "phase": "transmission",
        ...
    }
}
```

失败：
```json
{
    "outcome": "failure",
    "details": "错误详情",
    "report": { ... }
}
```

## 启动方式

运行根目录下的 `run_1052bot.py` 即可启动服务。默认端口为 10520。
